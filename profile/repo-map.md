# Repository map

The project is split into six repositories plus the organisation profile.
They are designed to be cloned side by side into one working directory; no
repository contains an absolute path from the author's machine, and no
repository contains a build product.

```
work/
  linux/       kernel: board support and the defconfig
  initramfs/   PID 1, rescue shell and the static tools it ships
  rootfs/      Arch Linux ARM payload and the installer that unpacks it
  tools/       host-side build, pack, flash, console and USB-network tools
  firmware/    vendor firmware blobs, sha256 manifest and notice
  mesa/        Mesa fork with the Adreno 825 device entry
  .github/     organisation profile and the progress chart
```

`tools`, `initramfs` and `rootfs` assume their siblings live in the parent
directory of the checkout; every path can be overridden (see the contract
table below).

## What each repository owns

| Repository | Default branch | Owns |
|---|---|---|
| `linux` | `Linux-7.2-MEIZU_22-M2582` | The kernel itself: board device trees (`arch/arm64/boot/dts/qcom/meizu-m2582-*.dtsi`, `tuna.dtsi`), the drivers the board needs, `arch/arm64/configs/meizu_m2582_defconfig`. Baseline branch `Linux-7.2` is the unmodified tree. |
| `initramfs` | `main` | Everything that runs before the distribution: `/init`, the rescue shell, the USB gadget script, the device helpers installed into the root (`m2582-adsp`, `m2582-bootok`, `m2582-reboot`), the static GPT editor `gpt-tool`, and the build scripts for static BusyBox, qbootctl and mke2fs. |
| `rootfs` | `main` | The Arch Linux ARM user space: download and repack scripts, the `payload/` tree that is appended under `/root/arch-bringup`, the Mesa patch, `install.sh`, `wipe-android.sh`, `repartition.sh`, and `build-images.sh`. |
| `tools` | `main` | The host workflow: `build-all.sh`, `build-kernel.sh`, `fetch-firmware.py`, `pack-boot.py`, serial console and USB-NCM file transfer, `BUILD.md`. |
| `firmware` | `main` | The vendor blobs the drivers ask for (GPU, video, WiFi, Bluetooth, touch, ADSP), `manifest.json` with size and sha256 per file, and `NOTICE.md`. |
| `mesa` | `meizu22-26.2.6` | A Mesa branch that adds the Adreno 825 device entry and advertises linear dma-buf modifiers only. Three commits on top of Mesa 26.2.6. |
| `.github` | `main` | `profile/README.md` (the organisation landing page) and `tools/progress/gen_tree.py`, which regenerates `profile/assets/progress-dark.svg`. |

## How the pieces fit

### Boot image

```
firmware/  --(fetch-firmware.py)-->  tools/firmware/
initramfs/ --(build-busybox/qbootctl/mke2fs)-->  initramfs/artifacts/
initramfs/ --(build-initramfs.py + tools/firmware)-->  initramfs/artifacts/initramfs/initramfs.cpio.gz
linux/     --(build-kernel.sh, embeds the cpio)-->  linux/out-meizu/arch/arm64/boot/Image
Image      --(pack-boot.py + your stock boot.img)-->  tools/out/boot.img
boot.img   --(fastboot flash boot_a/boot_b)-->  the phone
```

`tools/build-all.sh` drives steps 1-5 in one go. The initramfs archive is
embedded in `Image` (its path is written into `CONFIG_INITRAMFS_SOURCE`), so
the boot image carries the kernel, the device tree and the initramfs; it does
not carry the root filesystem.

### Root filesystem

```
fetch-rootfs.sh  ->  rootfs/downloads/ArchLinuxARM-aarch64-latest.tar.gz
prepare.sh       ->  rootfs/downloads/ArchLinuxARM-aarch64-latest.cpio.gz
                     rootfs/downloads/{install.sh,wipe-android.sh,mke2fs.conf,...}
build-images.sh  ->  rootfs/downloads/ARCH-RESCUE.img, ARCH-NORMAL.img
rescue boot      ->  install.sh in the initramfs shell  ->  ext4 on PARTNAME=linux
```

The root filesystem is never turned into a disk image for `fastboot`: the
board's bootloader cannot flash a multi-gigabyte ext4 image, so the archive is
streamed (`wget | gzip -dc | cpio -i`) into a filesystem created on the phone.
`build-images.sh` builds two boot images from the same kernel and initramfs;
only the built-in command line differs (`m2582.rootfs=none` for the rescue
image).

### GPU user space

`mesa` is independent of the boot image. The distribution's own Mesa has no
Adreno 825 entry, so the phone runs Mesa built from this branch. `rootfs` ships
the equivalent patch and the build script for the phone; the branch is the
reviewable form of the same three changes.

## Cross-repository contract

| Variable | Default | Consumed by | Meaning |
|---|---|---|---|
| `LINUX_DIR` | `../linux` | `tools` | kernel checkout to build and pack |
| `INITRAMFS_DIR` | `../initramfs` | `tools` | initramfs checkout that produces the cpio |
| `ROOTFS_DIR` | `../rootfs` | `tools/build-all.sh` | rootfs checkout (reported, not built) |
| `FIRMWARE_REPO` | `../firmware` | `tools` | firmware checkout or git URL to stage from |
| `FIRMWARE` | `./firmware` | `tools`, `initramfs` | staged firmware the build reads |
| `KERNEL_DIR` | `../linux` | `initramfs` | kernel tree, used to find `gen_init_cpio` |
| `GEN_INIT_CPIO` | unset | `initramfs` | exact `gen_init_cpio` path; set by `build-kernel.sh` |
| `KERNEL_TOOLS` | `../tools` | `rootfs` | tools checkout that builds and packs the images |
| `OEM_BOOT` | unset (required) | `rootfs/build-images.sh` | your stock `boot.img`, the AVB donor |
| `DEV` / `BASE_URL` | auto / `http://192.168.42.2:8000` | `rootfs/install.sh` | target partition and host HTTP root |

Artifacts exchanged between repositories:

| Produced by | Path | Consumed by |
|---|---|---|
| `initramfs/build-*.sh` | `initramfs/artifacts/{busybox,qbootctl,mke2fs}/` | `initramfs/build-initramfs.py` |
| `initramfs/build-initramfs.py` | `initramfs/artifacts/initramfs/initramfs.cpio{,.gz}` | kernel build (`CONFIG_INITRAMFS_SOURCE`), `pack-boot.py` verification |
| `tools/fetch-firmware.py` | `tools/firmware/` | `build-kernel.sh` -> initramfs packer |
| `build-kernel.sh` | `linux/out-meizu/arch/arm64/boot/Image` | `pack-boot.py` |
| `pack-boot.py` | `tools/out/boot.img`, `out/boot.json`, `out/boot.avb.txt` | `fastboot`, validation evidence |
| `rootfs/prepare.sh` | `rootfs/downloads/*.cpio.gz` and device scripts | the rescue shell installer |

## What is deliberately not in git

* **No root filesystem images or tarballs.** The ALARM tarball, the repacked
  cpio, the Mesa source release and the boot images are all downloaded or
  generated into `rootfs/downloads/`, which is ignored.
* **No vendor blobs in the code repositories.** Firmware lives only in the
  `firmware` repository, with a `NOTICE.md` that states the redistribution
  position. The kernel and tool repositories stage it into an ignored
  directory at build time.
* **No build products.** `linux/out-meizu/`, `initramfs/artifacts/`,
  `initramfs/build/`, `tools/out/` and `tools/firmware/` are ignored by the
  per-repository `.gitignore`.
* **Large downloads are pinned, not committed.** Where a build needs a file
  from the network, the expected digest or commit is in the script:

| Input | Pin |
|---|---|
| Arch Linux ARM rootfs tarball | sha256 `42a4eeaa...` (`rootfs/fetch-rootfs.sh`) |
| Mesa 26.2.6 source release | sha256 `b9436b3e...` (`rootfs/fetch-rootfs.sh`) |
| BusyBox 1.37.0 | sha256 `3311dff3...` (`initramfs/build-busybox.sh`) |
| e2fsprogs 1.47.2 | sha256 `08242e64...` (`initramfs/build-mke2fs.sh`) |
| qbootctl 0.2.2 | commit `8c6bc775...` (`initramfs/build-qbootctl.sh`) |
| vendor firmware | per-file sha256 in `firmware/manifest.json` |

## Where a change belongs

| Change | Repository |
|---|---|
| Driver, device tree, defconfig, kernel command line default | `linux` |
| Rescue behaviour, partition discovery, device-side boot helpers | `initramfs` |
| Distribution file layout, services, installer, Mesa build on the phone | `rootfs` |
| Build orchestration, image packing, host transfer tools | `tools` |
| GPU user-space driver | `mesa` |
| A firmware blob that is not already pinned | `firmware` (only if it may be redistributed) |
| Organisation page, status chart | `.github` |
