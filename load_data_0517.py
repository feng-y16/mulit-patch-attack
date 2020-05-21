import fnmatch
import math
import os
import sys
import time
from operator import itemgetter

import gc
import numpy as np
import torch
import torch.optim as optim
import torch.nn as nn
import torch.nn.functional as F
from PIL import Image
from torch.utils.data import Dataset
from torchvision import transforms




print('starting test read')
im = Image.open('data/horse.jpg').convert('RGB')
print('img read!')


def affine(theta, img_size, patch_aff):
    grid = F.affine_grid(theta, [theta.shape[0], 3, img_size, img_size])
    affine_result = F.grid_sample(patch_aff, grid).unsqueeze(0)
    return affine_result


class PatchTransformer(nn.Module):
    """PatchTransformer: transforms a list of patches

    Module providing the functionality necessary to transform a list of patches, put them at the location
    defined by a list of location.

    Output the img which is patched
    
    batch is not supported

    """

    def __init__(self):
        super(PatchTransformer, self).__init__()

    def forward(self, adv_patch_list, patch_location_list, img_size, img_clean):

        # clamp the range of patch pixel
        for patch_item_index in range(len(adv_patch_list)):
            patch_item = adv_patch_list[patch_item_index]
            # adv_patch_list[patch_item_index] = torch.clamp(patch_item, 0.000001, 0.99999)

        assert len(adv_patch_list) == len(patch_location_list)

        # prepare FloatTensor that will be used in affine
        theta = torch.cuda.FloatTensor(len(adv_patch_list), 2, 3).fill_(0)
        patch_aff_total = torch.cuda.FloatTensor()
        patch_mask_aff_total = torch.cuda.FloatTensor()


        for i in range(len(adv_patch_list)):

            patch_height = adv_patch_list[i].shape[1]
            patch_width = adv_patch_list[i].shape[2]
            assert patch_height <= img_size
            assert patch_width <= img_size

            # left_up_corner
            patch_x = int(patch_location_list[i][0]*img_size)
            patch_y = int(patch_location_list[i][1]*img_size)
            assert patch_x <= img_size
            assert patch_y <= img_size

            # Use affine translation to put the patch to the desired location

            # Prepare theta, affine matrix for i-th
            theta[i, 0, 0] = 1
            theta[i, 0, 1] = 0
            theta[i, 0, 2] = -patch_location_list[i][0]

            theta[i, 1, 0] = 0
            theta[i, 1, 1] = 1
            theta[i, 1, 2] = -patch_location_list[i][1]

            # Pre-process for affine
            # Complete the patch to the same size as img size, so the affine precess won't be wrong
            patch_aff = adv_patch_list[i]
            patch_aff = torch.cat([patch_aff, torch.cuda.FloatTensor(3, img_size-patch_height, patch_width).fill_(0)],
                                  1)
            patch_aff = torch.cat([patch_aff, torch.cuda.FloatTensor(3, img_size, img_size-patch_width).fill_(0)],
                                  2)
            patch_aff = patch_aff.unsqueeze(0)

            # Create a mask to cut-off the black edge.
            # The black edge is caused by Bilinear interpolation when affine.
            patch_mask_aff_ones = torch.ones_like(patch_aff)
            patch_mask_aff_zeros = torch.zeros_like(patch_aff)
            patch_mask_aff = torch.where(patch_aff >= 0, patch_mask_aff_ones, patch_mask_aff_zeros)

            # storage the patch_aff and patch_mask_aff to a large multi-channel tensor
            patch_mask_aff_total = torch.cat([patch_mask_aff_total, patch_mask_aff], dim=0)
            patch_aff_total = torch.cat([patch_aff_total, patch_aff], dim=0)

        # use theta and patch_aff_total to affine all patches.
        # Each patch has its own result
        patch_affine2 = affine(theta, img_size, patch_aff_total)

        # Use mask to cut off the black edge
        patch_mask_affine2 = affine(theta, img_size, patch_mask_aff_total)
        patch_mask_affine2_black = torch.cuda.FloatTensor(patch_mask_affine2.size()).fill_(0)
        patch_mask_affine2 = torch.where((patch_mask_affine2 == 1), patch_mask_affine2, patch_mask_affine2_black)

        # apply cut-off
        patch_affine2 = patch_affine2 * patch_mask_affine2

        # apply patches to the image
        advs = torch.unbind(patch_affine2, 1)
        img_patched = img_clean
        for adv in advs:
            img_patched = torch.where((adv == 0), img_patched, adv)  # zzj:注意存在边缘擦除的可能性

        return img_patched




if __name__ == '__main__':
    pass
