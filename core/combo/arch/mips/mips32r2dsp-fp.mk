# Configuration for Android on MIPS.
# Generating binaries for MIPS32R2/hard-float/little-endian/dsp

ARCH_MIPS_HAVE_DSP  	:=true
ARCH_MIPS_DSP_REV	:=1
ARCH_MIPS_HAVE_FPU       :=true
arch_variant_cflags := \
    -EL \
    -march=mips32r2 \
    -mtune=mips32r2 \
    -mips32r2 \
    -mhard-float \
    -mdsp

arch_variant_ldflags := \
    -EL
