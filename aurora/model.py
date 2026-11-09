import torch
from torch import nn
from torch.nn import functional as functional

from aurora.data import grid_shape


def convolution(input_channels, output_channels, stride=1):
    return nn.Sequential(
        nn.Conv2d(input_channels, output_channels, 3, stride=stride, padding=1, bias=False),
        nn.GroupNorm(8, output_channels),
        nn.SiLU(inplace=True),
        nn.Conv2d(output_channels, output_channels, 3, padding=1, bias=False),
        nn.GroupNorm(8, output_channels),
        nn.SiLU(inplace=True),
    )


class Aurora(nn.Module):
    def __init__(self, config):
        super().__init__()
        depth = grid_shape(config["voxel"])[2]
        width = config["model"]["width"]
        if width % 8:
            raise ValueError("Model width must be divisible by 8")
        self.stem = convolution(depth, width, 2)
        self.middle = convolution(width, width * 2, 2)
        self.deep = convolution(width * 2, width * 3, 2)
        self.deep_projection = nn.Conv2d(width * 3, width * 2, 1)
        self.middle_projection = nn.Conv2d(width * 2, width, 1)
        self.fusion = convolution(width, width)
        self.heatmap = nn.Conv2d(width, 1, 1)
        self.position = nn.Conv2d(width, 3, 1)
        nn.init.constant_(self.heatmap.bias, -4.595)

    def forward(self, voxels):
        shallow = self.stem(voxels)
        middle = self.middle(shallow)
        deep = self.deep(middle)
        middle = middle + functional.interpolate(self.deep_projection(deep), size=middle.shape[-2:], mode="bilinear", align_corners=False)
        merged = shallow + functional.interpolate(self.middle_projection(middle), size=shallow.shape[-2:], mode="bilinear", align_corners=False)
        features = self.fusion(merged)
        return {"heatmap": self.heatmap(features), "position": self.position(features)}


def detection_loss(prediction, batch, position_weight=2.0):
    probability = prediction["heatmap"].float().sigmoid().clamp(1e-5, 1 - 1e-5)
    target = batch["heatmap"]
    positive = target.eq(1).float()
    negative = target.lt(1).float()
    positive_loss = -(probability.log() * (1 - probability).pow(2) * positive)
    negative_loss = -((1 - probability).log() * probability.pow(2) * (1 - target).pow(4) * negative)
    count = positive.sum().clamp_min(1)
    heatmap_loss = ((positive_loss + negative_loss) * batch["heatmap_mask"]).sum() / count
    offsets = prediction["position"].float()
    offsets = torch.cat((offsets[:, :2].sigmoid(), offsets[:, 2:]), dim=1)
    regression = functional.smooth_l1_loss(offsets, batch["regression"], reduction="none")
    position_loss = (regression * batch["regression_mask"]).sum() / count
    return {"loss": heatmap_loss + position_weight * position_loss, "heatmap_loss": heatmap_loss, "position_loss": position_loss}


@torch.no_grad()
def decode(prediction, config):
    probability = prediction["heatmap"].float().sigmoid()
    peaks = functional.max_pool2d(probability, 3, stride=1, padding=1)
    probability = probability * probability.eq(peaks)
    batch_size, _, height, width = probability.shape
    count = min(config["top_k"], height * width)
    scores, indices = torch.topk(probability.reshape(batch_size, -1), count, dim=1)
    regression = prediction["position"].float().reshape(batch_size, 3, -1)
    selected = regression.gather(2, indices[:, None].expand(-1, 3, -1))
    columns, rows = indices % width, indices // width
    stride = config["voxel"]["output_stride"]
    cell_x, cell_y = [value * stride for value in config["voxel"]["size"][:2]]
    positions = torch.stack((
        config["voxel"]["range"][0] + (columns + selected[:, 0].sigmoid()) * cell_x,
        config["voxel"]["range"][1] + (rows + selected[:, 1].sigmoid()) * cell_y,
        selected[:, 2],
    ), dim=-1)
    results = []
    for batch_index in range(batch_size):
        detections = []
        for score, position in zip(scores[batch_index].cpu().tolist(), positions[batch_index].cpu().tolist()):
            if score >= config["score_threshold"]:
                detections.append({"label": "tunnel", "position": position, "score": score})
        results.append(detections)
    return results
