# Configuration for Android on MIPS.
# Generating binaries for MIPS32R2/hard-float/big-endian/dsp

ARCH_MIPS_HAVE_DSP  	:=true
ARCH_MIPS_DSP_REV	:=2
ARCH_MIPS_HAVE_FPU       :=true
ARCH_HAVE_BIGENDIAN	:=true
TARGET_YAFFS2_BIGENDIAN :=1
arch_variant_cflags := \
    -EB \
    -march=mips32r2 \
    -mtune=mips32r2 \
    -mips32r2 \
    -mhard-float \
    -mdspr2

arch_variant_ldflags := \
    -EB
