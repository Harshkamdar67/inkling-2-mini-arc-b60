#!/bin/bash
# With GGML_VK_DEVICE_NAME=B60 (patched ggml-vulkan) the B60 is the only Vulkan device, so it is always Vulkan0.
# Callers must export GGML_VK_DEVICE_NAME=B60. Index order without the filter is not stable between processes.
echo Vulkan0
