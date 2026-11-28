# Quick start

From a fresh x86_64 Linux host to KDE Plasma on a Meizu 22 (M2582,
Qualcomm SM8735). Every command below is meant to be copied; the commands
marked **on the phone** run in the serial console or in the initramfs rescue
shell, everything else runs on the host.

Read the warnings first. There is no dual boot and no way back to Android with
your data intact.

> **This procedure replaces the operating system.**
>
> * Android and dual boot are **not supported**. The first rescue-shell step
>   rewrites the partition table; on a stock phone it turns the single
>   `userdata` partition into the Arch root, destroying Android and all data
>   on it.
> * The bootloader must be unlocked and verified boot disabled. The images keep
>   the stock AVB header but cannot carry the vendor signature.
> * The phone exposes a single USB port. It is either the serial console or
>   fastboot, never both at the same time.

Expected total: a few hours, most of it downloads (Arch Linux ARM root
filesystem, KDE packages, Mesa). The individual timings are in
[validation.md](validation.md).

---

## 1. Host packages

The commands below assume Arch Linux x86_64, which is what the project was
built and tested on (clang 23.1.5, aarch64-linux-gnu-gcc 16.2.0,
qemu-aarch64-static 11.1.3). Other distributions work with the equivalent
packages.

```sh
sudo pacman -S --needed base-devel git curl python python-pyserial \
    clang lld llvm bc bison flex cpio rsync gzip xz \
    aarch64-linux-gnu-gcc aarch64-linux-gnu-binutils qemu-user-static \
    fakeroot libarchive erofs-utils mtools android-tools
```

What each group is for:

| Packages | Used for |
|---|---|
| `base-devel` `git` `curl` `python` | build scripts, downloads, Python tools (standard library only) |
| `clang` `lld` `llvm` `bc` `bison` `flex` `cpio` `rsync` `gzip` `xz` | kernel and initramfs build (`ARCH=arm64 LLVM=1`) |
| `aarch64-linux-gnu-gcc` / `-binutils`, `qemu-user-static` | static BusyBox, qbootctl and mke2fs; qemu executes them as a build-time check |
| `fakeroot` `libarchive` | root filesystem repack (root-owned files, `bsdtar` listing) |
| `android-tools` | `fastboot` |
| `python-pyserial` | `console.py`, `push-file.py`, `net-file.py`, `reboot-to-fastboot.py` |
| `erofs-utils` `mtools` | only for `fetch-firmware.py --images` (extracting firmware from your own factory images) |

Disk: about 30 GB free, plus 8 GiB under `rootfs/downloads/`.

**Evidence**: every tool answers.

```sh
clang --version | head -1
aarch64-linux-gnu-gcc --version | head -1
qemu-aarch64-static --version | head -1
fastboot --version | head -1
```

## 2. Clone the repositories side by side

All paths are relative to this parent directory; do not rename the checkouts.

```sh
mkdir -p ~/m2582 && cd ~/m2582
git clone -b Linux-7.2-MEIZU_22-M2582 https://github.com/MEIZU-22-SM8735-Development/linux.git
git clone https://github.com/MEIZU-22-SM8735-Development/initramfs.git
git clone https://github.com/MEIZU-22-SM8735-Development/rootfs.git
git clone https://github.com/MEIZU-22-SM8735-Development/firmware.git
git clone https://github.com/MEIZU-22-SM8735-Development/tools.git
git clone --depth 1 -b meizu22-26.2.6 https://github.com/MEIZU-22-SM8735-Development/mesa.git
```

**Evidence**: six directories exist and the tools can resolve them.

```sh
ls
cd tools
sh build-all.sh --check
```

`build-all.sh --check` prints the resolved paths of `linux`, `initramfs`,
`rootfs`, `firmware` and the staging directory, then ends with
`build-all: prerequisites ok (--check, nothing built)`. If it complains,
the checkout is missing or a host tool is not installed.

## 3. Get a stock `boot.img`

The packer needs a `boot.img` from **your own factory package**, of the same
firmware release as the phone. It is used only as the AVB header/footer donor:
the replacement kernel is unsigned and the phone must have verification
disabled. It is not distributed with this project.

Extract `boot.img` from the factory package you downloaded for your phone
(unpack the package; the image is usually named `boot.img`; do not flash
anything from it). Keep it outside the repositories, for example:

```sh
mkdir -p ~/stock && cd ~/stock
# unpack your factory package here until boot.img is available
ls -l boot.img
```

**Evidence**: it is a header-v4 boot image with an AVB footer. The packer
checks both and refuses anything else.

```sh
head -c 8 boot.img                          # ANDROID!
tail -c 64 boot.img | head -c 4             # AVBf
```

## 4. Build the kernel and initramfs

```sh
cd ~/m2582/tools
sh build-all.sh
```

It runs, in order: static BusyBox, qbootctl, mke2fs, firmware staging from
`../firmware` into `./firmware`, then the kernel with the initramfs embedded.
It prints the elapsed seconds per step and at the end the exact
`pack-boot.py` command. Do not run two builds at the same time.

**Evidence**:

```sh
ls -l ../linux/out-meizu/arch/arm64/boot/Image
ls -l ../initramfs/artifacts/initramfs/initramfs.cpio.gz
cat ../initramfs/artifacts/initramfs/build.json
grep -o 'meizu.build=[0-9-]*' ../linux/out-meizu/.config
```

`build.json` contains the BusyBox and cpio sha256 values. The last lines of
`build-all.sh` show the `pack-boot.py` command for a single image (the
fresh-install path in step 6 builds both images itself):

```sh
python3 pack-boot.py --original ~/stock/boot.img --output out/boot.img
```

The packer verifies that the `Image` config matches the build config, that the
initramfs is the one just built, that the DTB is linked in, and that the result
fits the stock partition. It writes `out/boot.img`, `out/boot.json` and
`out/boot.avb.txt`. `requires_disabled_verification` must be `true` in
`boot.json`.

## 5. Build the root filesystem archive

```sh
cd ~/m2582/rootfs
sh fetch-rootfs.sh            # ~860 MB download, sha256-pinned
sh prepare.sh                 # ~3 minutes, ~2.1 GB temporary
```

`fetch-rootfs.sh` downloads the Arch Linux ARM tarball and the Mesa 26.2.6
source release and verifies both against the pinned sha256. `prepare.sh`
appends `payload/`, the Mesa source and the ADSP firmware to the archive and
emits `downloads/ArchLinuxARM-aarch64-latest.cpio.gz` plus the scripts the
rescue shell downloads.

**Evidence**:

```sh
sh fetch-rootfs.sh --check
ls -l downloads/ArchLinuxARM-aarch64-latest.cpio.gz
ls -l downloads/install.sh downloads/wipe-android.sh downloads/mke2fs.conf
```

If you do not have the sibling `firmware` checkout, `prepare.sh --skip-firmware`
builds an archive without the ADSP firmware, but then the phone cannot report
battery state or charge correctly.

## 6. Build the rescue and normal boot images

```sh
cd ~/m2582/rootfs
OEM_BOOT=~/stock/boot.img sh build-images.sh
```

This builds the kernel twice, once with `m2582.rootfs=none` baked into the
command line (rescue) and once without it (normal), and packs both. The script
fails if the flag ends up in the wrong image.

**Evidence**:

```sh
ls -l downloads/ARCH-RESCUE.img downloads/ARCH-NORMAL.img
strings downloads/ARCH-RESCUE.img | grep -o 'm2582.rootfs=none'
strings downloads/ARCH-NORMAL.img | grep -c 'm2582.rootfs=none'   # 0
```

## 7. Flash the rescue image

Put the phone into fastboot. From Android: `adb reboot bootloader` or the key
combination. From a phone that already runs this system:

```sh
cd ~/m2582/tools
python3 console.py --password m2582 --timeout 12 \
    --cmd 'sync && /usr/local/bin/m2582-reboot bootloader'
```

Wait for enumeration and flash both slots. The slot A/B retry counters are
maintained by the initramfs afterwards, so no manual slot switching is needed.

```sh
until timeout 2 fastboot devices | grep -q .; do sleep 1; done
fastboot flash boot_a ~/m2582/rootfs/downloads/ARCH-RESCUE.img
fastboot flash boot_b ~/m2582/rootfs/downloads/ARCH-RESCUE.img
fastboot reboot
```

**Evidence** (serial console, 115200 8N1): the rescue mode announces itself,
offers a `#` prompt, and carries the static GPT helper used in step 9.

```
rescue: no usable distro root on /dev/sda24
rescue: usb0 is up at 192.168.42.1/24
```

```sh
ls -l /sbin/gpt-tool /sbin/mke2fs
```

If you see `distro root: using persistent rootfs ...` instead, the normal
image was flashed by mistake.

## 8. Host network and HTTP server

In a second host terminal, while the phone sits in the rescue shell:

```sh
cd ~/m2582/tools
sudo sh net-up.sh up
cd ~/m2582/rootfs
python3 -m http.server 8000 --bind 0.0.0.0 --directory downloads &
```

`net-up.sh` finds the gadget interface by its pinned MAC address and assigns
`192.168.42.2/24`; the phone is `192.168.42.1`.

**Evidence**: the host reaches the phone.

```sh
ping -c2 192.168.42.1
```

The package proxy (`serve-proxy.py`, port 3128) is only needed later, in
step 13. If your host already has an HTTP proxy, start the forwarder now and
point it at that proxy:

```sh
cd ~/m2582/rootfs
python3 serve-proxy.py --upstream 127.0.0.1:20171 &
```

The default upstream is `127.0.0.1:20171`, the proxy the development host
uses; a fresh machine does not have it. Replace it with your own proxy, or,
if the host has direct internet and no proxy, run any HTTP proxy bound to
`192.168.42.2:3128` (for example `tinyproxy` with `Listen 192.168.42.2` and
`Port 3128`). The direct-internet path is not exercised by this project.

## 9. Prepare the partition table (on the phone)

The initramfs and `install.sh` find the root filesystem by GPT partition name:
it must be called `linux`. Run this in the rescue shell before installing.

```sh
wget -q http://192.168.42.2:8000/repartition.sh -O /tmp/repartition.sh
sh /tmp/repartition.sh                 # read-only report of the layout
```

Two starting points, both first dry-runnable:

| Phone state before | Command | Effect |
|---|---|---|
| stock phone: `sda24` is `userdata`, no `sda25` | `sh /tmp/repartition.sh --adopt-userdata` | renames `sda24` to `linux`; `install.sh` formats it next, so Android and all its data are destroyed |
| dual layout: `sda24` is `linux`, `sda25` is `userdata` | `sh /tmp/repartition.sh --wipe-userdata` | keeps `linux`, deletes the retired data partition and frees the space for step 15 |

Add `--dry-run` to either flag to print the `gpt-tool` commands without
changing the table. The script only ever touches partitions 24 and 25, needs
an explicit flag for every change, and prints the table before and after.

**Evidence**: after a stock-phone adoption the kernel reports partition 24 as
`linux` (in the rescue shell there is no `sgdisk`; read the kernel's view):

```sh
for d in /sys/block/sda/sda*; do
    echo "$d $(sed -n 's/^PARTNAME=//p' "$d/uevent")";
done
```

Exactly one partition must report `linux`. If the old name is still there,
reboot into the rescue image once and re-run the script (the script says so).

If you want the old Android data blocks overwritten rather than merely
unreferenced, use the heavier variant instead of `--wipe-userdata`. It only
accepts partition 25 named `userdata`, and it also deletes that GPT entry:

```sh
wget -q http://192.168.42.2:8000/wipe-android.sh -O /tmp/wipe-android.sh
sh /tmp/wipe-android.sh --dry-run
sh /tmp/wipe-android.sh --yes           # prints when both regions read back as zeros
```

## 10. Install Arch (on the phone)

Format the partition named `linux` and stream the root filesystem into it.
Nothing is mounted in rescue mode, which is why the format happens here.

```sh
wget -q http://192.168.42.2:8000/install.sh -O /tmp/install.sh
sh /tmp/install.sh --dry-run
sh /tmp/install.sh
```

**Evidence**, in order: `mke2fs returned 0`, `cpio rc=0`, the unpacked package
count, and finally `all checks passed`. Unpacking writes about 2.1 GB and takes
one to three minutes; the console is silent during it.

## 11. Flash the normal image and cold boot

```sh
# on the phone, in the rescue shell
/usr/bin/m2582-reboot bootloader
```

```sh
# on the host
fastboot flash boot_a ~/m2582/rootfs/downloads/ARCH-NORMAL.img
fastboot flash boot_b ~/m2582/rootfs/downloads/ARCH-NORMAL.img
fastboot reboot
```

Power the phone fully off and on for the first boot: it removes one variable
from the display bring-up.

**Evidence**: the initramfs finds the new root, stage 1 starts, and a login
prompt appears. Log in as `root` with password `m2582`.

```
distro root: using persistent rootfs on /dev/sda24 (ext4, rw)
root handover: switch_root /mnt/diskroot /sbin/init
arch-init: stage 1 start
m2582 login:
```

## 12. First boot checks, then hand over to systemd

Stage 1 deliberately boots to a shell: if systemd dies as PID 1 there is no
second entry point on this board.

```sh
/usr/local/bin/verify-arch
```

Every line shows the actual value next to the expected one; anything unexpected
is marked `!!`. The root filesystem, distribution, USB network, DRM, backlight
and input devices should already be fine. The GPU check is the exception: it
reports `!! GPU probe` while neither `eglinfo` nor `eglprobe` is installed, and
`llvmpipe` until Mesa is built (step 14).

Once the checks look sane, enable systemd and reboot:

```sh
echo systemd > /etc/arch-init-systemd
reboot
```

**Evidence**:

```sh
cat /proc/1/comm                       # systemd
systemctl is-system-running            # running, or degraded
systemctl status serial-getty@ttyGS0   # active
```

`degraded` is expected: the board has no audio codec, camera or sensors yet.
If systemd does not reach multi-user twice in a row, stage 1 falls back to the
login shell; delete `/etc/arch-init-systemd` to stay there.

## 13. Network, full upgrade, then KDE

The root filesystem is an ALARM snapshot; the package repositories have moved
on since. **Run a full upgrade before installing anything else** - installing
single packages on top of the snapshot is a partial upgrade and breaks shared
libraries (a `libssl.so.4` mismatch in `wpa_supplicant` is the usual one).

Pick one network path:

* **WiFi (recommended):** install NetworkManager first, then join the network.
* **Host USB proxy:** keep `serve-proxy.py` and `usb0` from step 8 up.

The mirror used by this project is NJU:

```sh
printf 'Server = https://mirrors.nju.edu.cn/archlinuxarm/$arch/$repo\n' \
    > /etc/pacman.d/mirrorlist
```

USB-proxy path (from the stage-1 shell):

```sh
export http_proxy=http://192.168.42.2:3128 https_proxy=http://192.168.42.2:3128
pacman -Syu --noconfirm
pacman -S --needed --noconfirm networkmanager wpa_supplicant
systemctl enable --now NetworkManager
nmcli device wifi connect "<ssid>" password "<password>"
```

WiFi path: the base image has neither NetworkManager nor supplicant, so the
first `pacman` still needs the USB proxy (or any other way to get one package
set onto the phone); after that join the network as above and continue without
the proxy. `kde-install.sh` detects a working WiFi default route and uses it.

Then install KDE:

```sh
sh /root/arch-bringup/kde-install.sh
```

This installs `plasma-meta`, `konsole`, fonts, PipeWire, NetworkManager and the
Mesa build dependencies; roughly 1.5-2 GB, 20-60 minutes depending on the
network. Without the CJK fonts KDE renders interface elements as boxes, so
they are installed too. `setup.sh` already enabled `plasma-session.service`, so
the desktop starts on the next boot as the ordinary user `M2582` (initial
password `123`, `sudo` for system changes; change both passwords).

**Evidence**:

```sh
pacman -Q plasma-desktop plasma-workspace kwin
systemctl status serial-getty@ttyGS0
```

Then reboot; the panel should show the Plasma desktop, and touch should follow
the finger.

## 14. Build Mesa (the GPU needs its own build)

Arch Linux ARM's `mesa 26.2.6` has no Adreno 825 in its device table. The
loader rejects the chip and silently falls back to `llvmpipe`: EGL comes up and
the frame rate looks plausible, but nothing runs on the GPU.

The tested path runs on the phone and uses the source release plus the patch
that the root filesystem archive already carries. The script installs `llvm`
itself: llvmpipe needs LLVM, and meson otherwise stops with `LLVMPipe Gallium
driver requires LLVM`.

```sh
sh /root/arch-bringup/build-mesa.sh           # about 10-20 minutes on 8 cores
```

**Evidence**: the renderer must be `freedreno` / `Adreno (TM) 825`, never
`llvmpipe`. `mesa-utils` provides `eglinfo`; install it over WiFi.

```sh
pacman -S --needed mesa-utils
eglinfo -B | grep -iE 'vendor|renderer'
strings /usr/lib/libgallium-*.so | grep -m1 'Adreno (TM) 825'
```

The same three changes are maintained as a branch in the `mesa` repository
(`meizu22-26.2.6`, three commits on top of Mesa 26.2.6). To build from the
repository instead of the release tarball, check out that branch and use the
same meson options that `build-mesa.sh` prints; do not apply the patch on top
of the branch. That path is not exercised by the project. Any later
`pacman -Syu` that updates Mesa overwrites the build; re-run the script.

## 15. Grow the root filesystem into the freed Android space (optional)

`repartition.sh` or `wipe-android.sh` printed the `sgdisk` and `resize2fs`
commands for the actual start sector. Run them **inside Arch**, not in the
rescue shell, and stop at the first failure:

```sh
pacman -S --needed gptfdisk
sgdisk -d 25 -d 24 -n 24:<start sector of sda24>:0 -t 24:8300 -c 24:linux /dev/sda
partprobe /dev/sda
e2fsck -f /dev/sda24
resize2fs /dev/sda24
df -h /
```

Re-creating the partition at the same start sector keeps the filesystem intact,
and keeping the name `linux` is what lets the initramfs and `/etc/fstab` find
it again.

## 16. Verify

Run the full checklist in [validation.md](validation.md). The short version:

```sh
grep -o 'meizu.build=[0-9-]*' /proc/cmdline
cat /sys/class/drm/card0-DSI-1/enabled
cat /sys/class/remoteproc/remoteproc0/state
ip -br addr show usb0
ls /sys/class/bluetooth/
dmesg | grep -ci 'error\|fail'
```

## Troubleshooting

| Symptom | First thing to check |
|---|---|
| no `/dev/ttyACM0` | is the phone in Linux mode? `lsusb` should show `1d6b:0104` |
| `fastboot devices` is empty | poll instead of sleeping; check the cable and that the phone is really in fastboot |
| the rescue image boots the normal system | the wrong image was flashed; `strings ARCH-RESCUE.img \| grep m2582.rootfs=none` |
| `repartition.sh` refuses | read its `--help`; it only renames the partition you name or adopts `userdata` |
| `install.sh` refuses | the target partition is not named `linux`; re-check step 9 |
| `wget` fails in the rescue shell | the host `http.server` on port 8000 and `usb0` on both sides |
| `cpio rc != 0` | the archive was not built by `prepare.sh` |
| systemd never comes up | stage 1 falls back to the shell after two attempts; remove `/etc/arch-init-systemd` |
| black panel after a reboot | cold boot once, then check `card0-DSI-1/enabled` and the backlight |
| GPU reports `llvmpipe` | `build-mesa.sh` was not run, or a later package update replaced Mesa |
| pacman cannot reach a mirror | the host proxy is not running, or `usb0` lost its address |