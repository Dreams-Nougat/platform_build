# Undefined symbols can occur if a non-sanitized library links
# sanitizer static libraries. That's OK, because the executable
# always depends on the ASan runtime library, which defines these
# symbols.
ifeq (address,$(strip $(SANITIZE_TARGET)))
  ifeq (false, $(LOCAL_CLANG))
    LOCAL_ALLOW_UNDEFINED_SYMBOLS := true
  endif
endif


my_prefix := TARGET_
include $(BUILD_SYSTEM)/multilib.mk

ifndef my_module_multilib
# libraries default to building for both architecturess
my_module_multilib := both
endif

ifeq ($(my_module_multilib),both)
ifneq ($(LOCAL_MODULE_PATH),)
ifneq ($(TARGET_2ND_ARCH),)
$(warning $(LOCAL_MODULE): LOCAL_MODULE_PATH for shared libraries is unsupported in multiarch builds, use LOCAL_MODULE_RELATIVE_PATH instead)
endif
endif

ifneq ($(LOCAL_UNSTRIPPED_PATH),)
ifneq ($(TARGET_2ND_ARCH),)
$(warning $(LOCAL_MODULE): LOCAL_UNSTRIPPED_PATH for shared libraries is unsupported in multiarch builds)
endif
endif
endif # my_module_multilib == both


LOCAL_2ND_ARCH_VAR_PREFIX :=
include $(BUILD_SYSTEM)/module_arch_supported.mk

ifeq ($(my_module_arch_supported),true)
include $(BUILD_SYSTEM)/shared_library_internal.mk
endif

ifdef TARGET_2ND_ARCH

LOCAL_2ND_ARCH_VAR_PREFIX := $(TARGET_2ND_ARCH_VAR_PREFIX)
include $(BUILD_SYSTEM)/module_arch_supported.mk

ifeq ($(my_module_arch_supported),true)
# Build for TARGET_2ND_ARCH
OVERRIDE_BUILT_MODULE_PATH :=
LOCAL_BUILT_MODULE :=
LOCAL_INSTALLED_MODULE :=
LOCAL_MODULE_STEM :=
LOCAL_BUILT_MODULE_STEM :=
LOCAL_INSTALLED_MODULE_STEM :=
LOCAL_INTERMEDIATE_TARGETS :=

include $(BUILD_SYSTEM)/shared_library_internal.mk

endif

LOCAL_2ND_ARCH_VAR_PREFIX :=

endif # TARGET_2ND_ARCH

my_module_arch_supported :=

###########################################################
## Copy headers to the install tree
###########################################################
include $(BUILD_COPY_HEADERS)
