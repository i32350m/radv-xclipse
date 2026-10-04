import re, pathlib, sys

def rd(p): return pathlib.Path(p).read_text()
def wr(p, s): pathlib.Path(p).write_text(s)

# 1) logging always on (level 2) so no environment variable / adb is needed
p = "src/amd/common/radv_log_helper.c"
s = rd(p)
anchor = "ac_xclipse_log_level(void)\n{\n"
assert anchor in s, "log level anchor not found"
s = s.replace(anchor, anchor + "   return 2; /* DIAG BUILD: always verbose */\n", 1)
wr(p, s)

# 2) native stderr never reaches logcat on Android: send it there
LOG = '__android_log_print(ANDROID_LOG_ERROR, "RADV_XCLIPSE", '
for p in ["src/amd/common/ac_gpu_info.c", "src/amd/vulkan/radv_physical_device.c"]:
    s = rd(p)
    n = s.count("fprintf(stderr, ")
    s = s.replace("fprintf(stderr, ", LOG)
    if "android/log.h" not in s:
        s = '#ifdef __ANDROID__\n#include <android/log.h>\n#endif\n' + s
    wr(p, s)
    print(p, "stderr->logcat:", n)

# 3) extra markers in the device enumeration path
p = "src/amd/vulkan/radv_physical_device.c"
s = rd(p)
def ins_after(s, anchor, text):
    assert s.count(anchor) == 1, "anchor not unique/found: " + anchor
    return s.replace(anchor, anchor + "\n" + text, 1)
def ins_before(s, anchor, text):
    assert s.count(anchor) == 1, "anchor not unique/found: " + anchor
    return s.replace(anchor, text + "\n" + anchor, 1)

D = '__android_log_print(ANDROID_LOG_ERROR, "RADV_XCLIPSE", '
s = ins_after(s, "   bool supported_device = false;",
  "   " + D + '"[940DIAG] enumerate: bustype=%d available_nodes=0x%x", (int)device->bustype, (unsigned)device->available_nodes);')
s = ins_after(s, "\n   const char *path = drm_device->nodes[DRM_NODE_RENDER];",
  "   " + D + '"[940DIAG] try_create: render node=%s", path ? path : "(null)");')
s = ins_after(s, "   version = drmGetVersion(fd);",
  "   " + D + '"[940DIAG] kernel drm driver name=\'%s\'", version ? version->name : "(null)");')
s = ins_before(s, "   /* Allow all devices on a virtual winsys, otherwise do a basic support check. */",
  "   " + D + '"[940DIAG] chip: family=%d gfx_level=%d pci_id=0x%x xclipse_model=%d", (int)pdev->info.family, (int)pdev->info.gfx_level, (unsigned)pdev->info.pci_id, (int)pdev->info.xclipse_model);')
wr(p, s)

# 4) show which SoC string the model detection sees
p = "src/amd/common/ac_gpu_info.c"
s = rd(p)
anchor = "   if (device_id != 0x73a0)"
s = ins_before(s, anchor,
  "   " + D + '"[940DIAG] detect_model: device_id=0x%x chip_rev=0x%08x", (unsigned)device_id, (unsigned)chip_rev);')
wr(p, s)
print("patched OK")

# ---- v2: first real fix for the Xclipse 940 -------------------------------------------------
# The kernel reports family 147 (MGFX) with external_rev 0x02600200 on the 940, far outside the
# 0x01..0xFF range the VANGOGH identification expects (530: 0x0A, 920: 0x80). That made
# ac_identify_chip() fail with "unknown (family_id, chip_external_rev): (147, 39846400)".
p = "src/amd/common/ac_gpu_info.c"
s = rd(p)

a = "(0x01..0xFF) matches both. */\n         identify_chip(VANGOGH);"
assert s.count(a) == 1, "MGFX identify anchor"
s = s.replace(a, a + "\n" +
    "         if (info->family == CHIP_UNKNOWN) {\n"
    "            " + D + '"[940FIX] MGFX external_rev 0x%x outside VANGOGH range -> forcing CHIP_VANGOGH", (unsigned)device_info->external_rev);\n'
    "            info->family = CHIP_VANGOGH;\n"
    "         }", 1)

a = "   info->chip_external_rev = device_info->external_rev;"
assert s.count(a) == 1, "chip_external_rev anchor"
s = s.replace(a,
    "   info->chip_external_rev = device_info->external_rev;\n"
    "   if (device_info->family == FAMILY_MGFX && info->chip_external_rev > 0xFF) {\n"
    "      " + D + '"[940FIX] chip_external_rev 0x%x -> 0x0A for addrlib", (unsigned)info->chip_external_rev);\n'
    "      info->chip_external_rev = 0x0A;\n"
    "   }", 1)

a = "   /* Gfx6-8 don't set ip_discovery_version. */"
assert s.count(a) == 1, "ip version anchor"
s = s.replace(a,
    "   " + D + '"[940DIAG] ip_type=%d kernel hw_ip_version=%u.%u ip_discovery=0x%x rings=0x%x family=%u ext_rev=0x%x", (int)ip_type, (unsigned)ip_info->hw_ip_version_major, (unsigned)ip_info->hw_ip_version_minor, (unsigned)ip_info->ip_discovery_version, (unsigned)ip_info->available_rings, (unsigned)device_info->family, (unsigned)device_info->external_rev);\n'
    + a, 1)
wr(p, s)
print("v2 fix patched")
