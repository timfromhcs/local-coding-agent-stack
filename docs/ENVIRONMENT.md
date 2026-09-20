# System Environment & Reconnaissance

This document records the exact hardware and software environment used during development, testing, and verification of the Local Coding Agent Stack.

## Hardware Specifications

| Component | Specification | Notes |
| :--- | :--- | :--- |
| **Operating System** | Microsoft Windows 11 Pro (Build 10.0.26200, 64-bit) | Host OS |
| **CPU** | AMD Ryzen 7 7735HS with Radeon Graphics | 8 Cores, 16 Logical Processors |
| **System Memory (RAM)** | ~20 GB (Total Visible: 20,748,000 KB) | ~11.8 GB available at baseline |
| **Primary GPU** | AMD Radeon(TM) Graphics (iGPU / RDNA2 680M) | Driver 26.6.1, AMD Proprietary |
| **GPU Architecture** | Integrated GPU (UMA - Unified Memory Architecture) | Shared system RAM via host memory |
| **Storage (Drive E:)** | Dedicated NVMe / SSD partition | ~470 GB free |
| **Storage (Drive C:)** | System drive | ~116 GB free |

## Toolchain & Runtime Inventory

| Tool / Runtime | Version | Path / Provider | Verification Status |
| :--- | :--- | :--- | :--- |
| **Python** | 3.14.6 | `C:\Program Files\Python314\python.exe` | Verified |
| **Node.js** | v22.23.1 | Standard PATH | Verified |
| **npm** | 10.9.8 | Standard PATH | Verified |
| **bun** | 1.4.2 | Installed via global npm / PATH | Verified |
| **Git** | 2.54.0.windows.1 | Standard PATH | Verified |
| **GitHub CLI (`gh`)** | 2.97.0 | Authenticated user `timfromhcs` | Verified |
| **CMake** | 4.4.0 | Kitware | Verified |
| **C/C++ Compiler** | MSVC v143 (Visual Studio 2022 Community 17.14) & Clang 21.0.0 | VS 2022 vcvars64 / ROCm 7.1 | Verified |
| **Vulkan SDK** | 1.4.357.0 | `C:\VulkanSDK\1.4.357.0` (`glslc`, `glslangValidator`) | Verified |
| **Vulkan Runtime** | Vulkan 1.4.315 (Device apiVersion) | AMD Proprietary Driver 2.0.353 | Verified via `vulkaninfo` |
| **Docker Desktop** | 29.6.1 | Docker CLI installed; WSL2 backend available | Verified |
| **WSL2** | Ubuntu-22.04 / Ubuntu | Microsoft WSL2 Kernel | Available |

## Known Environmental Limitations & Design Decisions

1. **Integrated GPU (AMD Radeon 680M)**:
   - Does not possess dedicated VRAM (uses host system memory pool).
   - In Vulkan backend builds, `GGML_VK_PREFER_HOST_MEMORY=1` is recommended to prevent allocation fragmentation in integrated VRAM apertures.
   - For ultra-fast drafting or low-memory profiles, CPU multi-threading (16 threads AVX2/FMA) serves as an alternative backend with low latency.
2. **Multi-Platform Support**:
   - Primary builds target native Windows 11 with Vulkan SDK and MSVC / Clang.
   - Secondary builds and container execution target Linux (Ubuntu 24.04 / 22.04) with glibc, libvulkan-dev, and CPU fallback paths.
3. **No Mock Testing**:
   - In accordance with non-negotiable rule #1 and #2, all tests run against actual binaries, real model weights, real proxy servers, and filesystem operations.
