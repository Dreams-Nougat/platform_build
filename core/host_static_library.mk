###########################################################
## Standard rules for building a static library for the host.
##
## Additional inputs from base_rules.make:
## None.
##
## LOCAL_MODULE_SUFFIX will be set for you.
###########################################################

ifeq ($(or $(USE_CLANG),$(USE_HOST_CLANG)),1)
  include $(BUILD_SYSTEM)/use_clang.mk
endif

ifeq ($(strip $(LOCAL_MODULE_CLASS)),)
LOCAL_MODULE_CLASS := STATIC_LIBRARIES
endif
ifeq ($(strip $(LOCAL_MODULE_SUFFIX)),)
LOCAL_MODULE_SUFFIX := .a
endif
ifneq ($(strip $(LOCAL_MODULE_STEM)$(LOCAL_BUILT_MODULE_STEM)),)
$(error $(LOCAL_PATH): Cannot set module stem for a library)
endif
LOCAL_UNINSTALLABLE_MODULE := true

LOCAL_IS_HOST_MODULE := true

include $(BUILD_SYSTEM)/binary.mk

$(LOCAL_BUILT_MODULE): $(built_whole_libraries)
$(LOCAL_BUILT_MODULE): $(all_objects)
	$(transform-host-o-to-static-lib)

ifeq ($(or $(USE_CLANG),$(USE_HOST_CLANG)),1)
  include $(BUILD_SYSTEM)/restore_compiler.mk
endif
