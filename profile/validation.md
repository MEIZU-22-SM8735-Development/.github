# Validation checklist

This is the clean-room acceptance procedure: it proves that a third party,
starting from the six public repositories and their own phone, can reproduce
the documented system. Run it on a fresh machine and a phone that has not been
prepared by the original developer.

Record every command and its output. The acceptance decision is based on the
evidence listed under each step, not on "it looked fine".

## 1. Prerequisites

Record these before building anything:

```sh
uname -a
cat /etc/os-release | head -3
clang --version | head -1
aarch64-linux-gnu-gcc --version | head -1
qemu-aarch64-static --version | head -1
python3 --version
fastboot --version | head -1
df -h ~
```

| Item | Required value | Recorded |
|---|---|---|
| Host | x86_64 Linux, network access | |
| Free disk | at least 30 GB, plus 8 GiB under `rootfs/downloads/` | |
| clang/LLD | new enough for the kernel build (23.1.5 was used) | |
| aarch64 cross compiler | `aarch64-linux-gnu-gcc`, or `CROSS_COMPILE` set | |
| qemu-aarch64-static | optional; only used by the build-time checks | |
| Phone | Meizu 22 (M2582, SM8735) | |
| Bootloader | unlocked, verification disabled | |
| Factory package | the same firmware release as the phone; contains `boot.img` | |
| Stock `boot.img` | header v4, AVB footer; sha256 recorded | |

Record the exact revisions and inputs:

```sh
cd ~/m2582
for r in linux initramfs rootfs firmware tools mesa; do
    printf '%-10s %s %s\n' "$r" \
        "$(git -C "$r" rev-parse --abbrev-ref HEAD)" \
        "$(git -C "$r" rev-parse HEAD)";
done
sha256sum ~/stock/boot.img
strings ~/stock/boot.img | grep -m1 -o 'Flyme[^*]*' || true
```

**Pass**: six repositories at the expected branches (`linux` on
`Linux-7.2-MEIZU_22-M2582`, `mesa` on `meizu22-26.2.6`, the rest on `main`),
and the stock image passes the v4/AVB checks from
[quickstart.md](quickstart.md) step 3.

## 2. Timings

Approximate reference values on an 8-core x86_64 host. The build scripts print
their own elapsed seconds; copy the real values into the last column.

| Step | Reference | Your value |
|---|---|---|
| clone all six repositories | 1-5 min (Mesa is the large one) | |
| static BusyBox | under 1 min | |
| qbootctl | under 1 min | |
| mke2fs | 1-2 min | |
| kernel + initramfs (`build-all.sh`) | 5-20 min, host dependent | |
| rootfs download (~860 MB) | network dependent | |
| `prepare.sh` | about 3 min | |
| `build-images.sh` (two kernel builds) | two times the kernel build | |
| rescue-mode boot to shell | under 30 s | |
| `install.sh` (format + 2.1 GB unpack) | format seconds, unpack 1-3 min | |
| normal boot to login prompt | 30-60 s | |
| KDE install (1.5-2 GB over USB) | 30-60 min | |
| Mesa build on the phone | 10-20 min | |
| whole procedure | 1.5-3 h plus downloads | |

## 3. Host artifacts

No phone is needed for this stage.

```sh
cd ~/m2582/tools
sh build-all.sh --check
sh build-all.sh 2>&1 | tee ~/build-all.log
ls -l ../linux/out-meizu/arch/arm64/boot/Image
sha256sum ../linux/out-meizu/arch/arm64/boot/Image
cat ../initramfs/artifacts/initramfs/build.json
```

**Evidence**: `build-all.log` ends with the pack command and the elapsed
seconds; `Image` and `initramfs.cpio.gz` exist; `build.json` reports a
`cpio_sha256` and a `busybox_sha256`.

Packing (if you also built the single normal image):

```sh
python3 pack-boot.py --original ~/stock/boot.img --output out/boot.img
cat out/boot.json
sha256sum out/boot.img out/boot.avb.txt
```

**Evidence**: `boot.json` contains `kernel_sha256`, `partition_bytes`,
`embedded_dtb_verified: true`, `embedded_initramfs_verified: true` and
`requires_disabled_verification: true`.

Root filesystem archive and both boot images:

```sh
cd ~/m2582/rootfs
sh fetch-rootfs.sh --check
sh prepare.sh 2>&1 | tee ~/prepare.log
OEM_BOOT=~/stock/boot.img sh build-images.sh 2>&1 | tee ~/build-images.log
sha256sum downloads/ArchLinuxARM-aarch64-latest.cpio.gz
sha256sum downloads/ARCH-RESCUE.img downloads/ARCH-NORMAL.img
strings downloads/ARCH-RESCUE.img | grep -o 'm2582.rootfs=none'
strings downloads/ARCH-NORMAL.img | grep -c 'm2582.rootfs=none'
```

**Evidence**: `prepare.log` prints the cpio entry count and sha256; the rescue
image contains `m2582.rootfs=none`, the normal image does not (count 0).

## 4. Rescue boot and repartition

Flash `ARCH-RESCUE.img` as described in [quickstart.md](quickstart.md) steps
7-8, then capture the boot log and run the GPT step.

```sh
cd ~/m2582/tools
python3 console.py --boot --seconds 60 > ~/rescue-boot.log
grep -E 'rescue:|distro root:' ~/rescue-boot.log
```

**Evidence**: `rescue: no usable distro root on /dev/sda24` (or
`distro root: skipped (m2582.rootfs=none)`) and
`rescue: usb0 is up at 192.168.42.1/24`. A line saying `using persistent
rootfs` means the normal image was flashed instead.

On the phone (rescue shell), dry-run and then apply the GPT step from
[quickstart.md](quickstart.md) step 9:

```sh
for d in /sys/block/sda/sda*; do
    echo "$d $(sed -n 's/^PARTNAME=//p' "$d/uevent")";
done
```

**Evidence**: exactly one partition reports `linux`. Record the before and
after output of the repartition script.

## 5. Installation

In the rescue shell, with the host HTTP server running:

```sh
wget -q http://192.168.42.2:8000/install.sh -O /tmp/install.sh
sh /tmp/install.sh --dry-run
sh /tmp/install.sh
```

**Evidence**: `mke2fs returned 0`, `cpio rc=0`, the expected package count,
`all checks passed`. Capture the console output on the host (`console.py
--cmd 'sh /tmp/install.sh'`) if you need it as evidence.

## 6. Normal boot and core system

Flash `ARCH-NORMAL.img` to both slots, cold boot, and capture:

```sh
python3 console.py --boot --seconds 45 > ~/normal-boot.log
python3 console.py --password m2582 --cmd 'uname -a; cat /proc/cmdline' > ~/cmdline.txt
```

Then, on the phone:

```sh
grep -o 'meizu.build=[0-9-]*' /proc/cmdline      # must match the build stamp
cat /sys/class/drm/card0-DSI-1/status             # connected
cat /sys/class/drm/card0-DSI-1/enabled            # enabled
cat /sys/class/backlight/ae94000.dsi.0/brightness # <= 320
findmnt -no SOURCE,FSTYPE,SIZE /                  # /dev/sda24 ext4
. /etc/os-release; echo $PRETTY_NAME              # Arch Linux ARM
cat /sys/class/remoteproc/remoteproc0/state       # running
cat /sys/class/power_supply/qcom-battmgr-bat/capacity  # a real percentage
ip -br addr show usb0                             # 192.168.42.1/24
dmesg | grep -ci 'error\|fail'                    # compare with the baseline
```

**Evidence**: the build stamp matches `build-all.log`; the panel is on with a
backlight at most 320; the root is the ext4 partition named `linux`; the ADSP
is `running` and battery capacity is a plausible number (not `Resource
temporarily unavailable`).

| Check | Expected | Pass |
|---|---|---|
| `meizu.build` | equals the stamp printed by the build | |
| DSI connector | `connected`, `enabled` | |
| backlight | at most 320 | |
| root filesystem | `/dev/sda24 ext4` | |
| distribution | `Arch Linux ARM` | |
| PID 1 | `systemd` after the hand-over | |
| USB network | `usb0 192.168.42.1/24` | |
| ADSP | `remoteproc0/state` = `running` | |
| battery | a percentage and a voltage | |
| keys | `/proc/bus/input/devices` lists `pmic_pwrkey` and `pmic_resin` | |

## 7. Display, GPU and touch

```sh
ls /dev/dri/card0 /dev/dri/renderD128
pacman -S --needed mesa-utils
eglinfo -B | grep -iE 'vendor|renderer'      # freedreno / Adreno (TM) 825
strings /usr/lib/libgallium-*.so | grep -m1 'Adreno (TM) 825'
dmesg | grep -ci hangcheck                   # 0
ls /dev/input/event*                          # touch + keys
grep -E 'Name=|Handlers=' /proc/bus/input/devices
```

**Evidence**: the renderer is `freedreno` / `Adreno (TM) 825` and never
`llvmpipe`; no hangcheck resets; the panel shows the four-colour full-screen
band test without missing or duplicated rows; touch follows the finger.

## 8. WiFi, Bluetooth, DisplayPort

```sh
systemctl enable --now NetworkManager        # installed but not enabled by kde-install.sh
nmcli device wifi connect "<ssid>" password "<password>"
ip -br addr show wlp1s0
nmcli -t -f DEVICE,STATE,CONNECTION device
ping -c3 1.1.1.1                              # once WiFi is associated
ls /sys/class/bluetooth/                      # hci0
bluetoothctl show                             # powered, factory address
cat /sys/class/drm/card0-DP-1/status          # connected, with a monitor plugged in
```

**Evidence**: `wlp1s0` exists and associates; `hci0` exists and
`bluetoothctl show` reports a controller that is not a random address (the
factory address comes from the `mzkv` partition); with a USB-C monitor
attached, `card0-DP-1` reports `connected` and the external display shows a
picture.

## 9. Iris video decode

```sh
pacman -S --needed v4l-utils ffmpeg
ls /dev/video*
v4l2-ctl --list-devices
v4l2-ctl -d /dev/video0 --list-formats-out    # H264, HEVC, VP90, AV01
```

Decode one file with the hardware decoder and compare the raw frames with a
software decode of the same file:

```sh
ffmpeg -c:v h264_v4l2m2m -i sample.mp4 -f rawvideo -pix_fmt nv12 /tmp/hw.nv12
ffmpeg -c:v h264 -i sample.mp4 -f rawvideo -pix_fmt nv12 /tmp/sw.nv12
sha256sum /tmp/hw.nv12 /tmp/sw.nv12
dmesg | grep -cE 'qcom-iris.*(fail|error)'    # 0
```

Use `hevc_v4l2m2m` instead of `h264_v4l2m2m` to exercise HEVC. The two sha256
values must match; if the frame counts differ, add `-fps_mode passthrough` to
both commands (raw streams carry no timestamps).

**Evidence**: the decoder nodes and formats are listed, both sha256 values are
identical, and there is no Iris error in `dmesg`.

## 10. Thermal, storage and error audit

```sh
for z in /sys/class/thermal/thermal_zone*/temp; do
    printf '%s ' "$(($(cat "$z") / 1000))";
done; echo
for c in /sys/class/thermal/cooling_device*/cur_state; do
    printf '%s ' "$(cat "$c")";
done; echo
findmnt -no SOURCE,FSTYPE,USED,AVAIL /          # UFS, ext4
dd if=/dev/zero of=/root/ufs-test bs=1M count=256 conv=fsync
sync; rm -f /root/ufs-test
dmesg > /tmp/dmesg.txt
grep -ci 'error\|fail' /tmp/dmesg.txt
grep -iE 'oops|panic|BUG:|watchdog' /tmp/dmesg.txt
```

**Evidence**: the temperatures are plausible, at least one cooling device can
be driven (writing a lower trip point and watching `cur_state` change is the
documented check), a 256 MB write completes without errors, and the error
count is not above the reference baseline. The reference build logs about 31
lines matching `error\|fail`; they are known noise (SPMI, dwc3, geni_i2c, the
aux bridge, GPU PDC/sqe firmware, an early backlight `-EINVAL`). The criterion
is *no new class of message*, not zero.

## 11. Evidence bundle

Keep these files; they are what makes the result reproducible:

| File | How to capture |
|---|---|
| repository revisions | the `for r in ...` loop in section 1 |
| stock `boot.img` sha256 | `sha256sum` |
| `build-all.log`, `prepare.log`, `build-images.log` | `tee` in section 3 |
| `out/boot.json`, `out/boot.avb.txt` | written by `pack-boot.py` |
| `initramfs/artifacts/initramfs/build.json` | written by the initramfs packer |
| `rescue-boot.log`, `normal-boot.log` | `console.py --boot` |
| `dmesg.txt` | copied off the phone |
| `verify-arch` output | `console.py --cmd /usr/local/bin/verify-arch` |

## 12. Failure modes

| Symptom | First check |
|---|---|
| `build-all.sh --check` fails | a sibling checkout or host tool is missing; the message names it |
| `pack-boot.py` refuses `--original` | the stock image is not header v4 or has no AVB footer |
| `net-up.sh` cannot find the interface | the phone is not in Linux/rescue mode; `lsusb` should show `1d6b:0104` |
| rescue boot shows `using persistent rootfs` | `ARCH-NORMAL.img` was flashed instead of `ARCH-RESCUE.img` |
| `repartition.sh` refuses | read `--help`; on a stock phone the adoption mode is required |
| `install.sh` refuses | no partition named `linux`; the GPT step did not run |
| `wget` fails in the rescue shell | host `http.server` on port 8000, and `usb0` up on both sides |
| `cpio rc != 0` | the archive was not produced by `prepare.sh` |
| no login prompt after the normal image | was `ARCH-NORMAL.img` flashed to both slots? |
| systemd never reaches multi-user | stage 1 falls back to the shell after two attempts; remove `/etc/arch-init-systemd` |
| black panel | cold boot once; then check `card0-DSI-1/enabled` and the backlight |
| GPU reports `llvmpipe` | `build-mesa.sh` was not run, or a package update replaced Mesa |
| `remoteproc0` is `offline` | ADSP firmware missing from the rootfs (`/lib/firmware/qcom/tuna`) |
| no `/dev/video*` | Iris probe failed; `dmesg \| grep -i iris` and check the video firmware |
| WiFi interface missing | vendor WiFi firmware missing from the initramfs; `dmesg \| grep ath12k` |
| Bluetooth controller missing | check `dmesg \| grep -i qca`; the UART is SE14 in the device tree |

## 13. Pass criteria

The reproduction passes when all of the following hold:

* all six repositories are at the recorded revisions, the build completes with
  exit 0 and the packer's JSON reports the embedded DTB and initramfs verified;
* the rescue image reaches the rescue shell and the normal image reaches the
  login prompt, with the command-line build stamp matching the build log;
* `install.sh` completes all eight steps and `setup.sh` reports
  `all checks passed`;
* the root filesystem is the ext4 partition named `linux`, systemd is PID 1,
  and `serial-getty@ttyGS0` is active;
* the DSI panel is enabled with a backlight at most 320, touch works, and the
  GPU renderer is `freedreno` / `Adreno (TM) 825`;
* `remoteproc0` is `running`, battery capacity reads back, WiFi associates and
  `hci0` exists;
* hardware decode produces byte-identical frames to software decode and there
  is no Iris error in `dmesg`;
* the `dmesg` error count shows no new class of message compared with the
  reference baseline.

Anything that does not hold is either a failure of reproduction or a known
limitation listed in the [README](README.md); record which one.
## Issues found and fixed by the first clean-room install (2026-11-28)

These were discovered by installing from scratch on hardware, not by reading
the scripts; all fixes are in the repositories:

1. **`/init` refused a valid root**: the distro's `/sbin/init` is an absolute
   symlink (`/root/arch-bringup/init-firstboot`), which does not resolve before
   `switch_root`, so `[ -x /mnt/diskroot/sbin/init ]` failed and the boot fell
   back to the rescue shell. The initramfs now resolves the symlink target
   inside the distro root.
2. **KDE did not start at boot**: `setup.sh` symlinked
   `plasma-session.service` into `multi-user.target.wants` without installing
   the unit itself. Fixed; `systemctl is-enabled plasma-session` is now the
   check.
3. **Mesa build stopped at `LLVMPipe Gallium driver requires LLVM`**: the
   llvmpipe fallback needs LLVM even when built explicitly. `build-mesa.sh`
   installs `llvm` and passes `-Dllvm=enabled`.
4. **Partial upgrade broke `wpa_supplicant`**: installing NetworkManager on top
   of the ALARM snapshot pulled a `libssl.so.4` dependency the snapshot did not
   have. The documented flow now runs `pacman -Syu` first (full upgrade); the
   NJU mirror is the project default.
5. **gpt-tool assumed 512-byte sectors**: the phone's UFS reports 4096, so
   `gpt-tool list /dev/sda` said "no GPT here". The tool now uses
   `BLKSSZGET` on block devices.
