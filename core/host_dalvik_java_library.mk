#
# Copyright (C) 2013 The Android Open Source Project
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

#
# Rules for building a host dalvik java library. These libraries
# are meant to be used by a dalvik VM instance running on the host.
# They will be compiled against libcore and not the host JRE.
#

ifeq ($(HOST_OS),linux)
USE_CORE_LIB_BOOTCLASSPATH := true

#################################
include $(BUILD_SYSTEM)/configure_local_jack.mk
#################################

#######################################
include $(BUILD_SYSTEM)/host_java_library_common.mk
#######################################
ifeq ($(LOCAL_IS_STATIC_JAVA_LIBRARY),true)
  # For static library, $(LOCAL_BUILT_MODULE) is $(full_classes_jack).
  LOCAL_BUILT_MODULE_STEM := classes.jack
endif

ifneq ($(LOCAL_NO_STANDARD_LIBRARIES),true)
  LOCAL_JAVA_LIBRARIES :=  core-oj-hostdex core-libart-hostdex $(LOCAL_JAVA_LIBRARIES)
endif

full_classes_jack := $(intermediates.COMMON)/classes.jack
jack_check_timestamp := $(intermediates.COMMON)/jack.check.timestamp
built_dex := $(intermediates.COMMON)/classes.dex

LOCAL_INTERMEDIATE_TARGETS += \
    $(full_classes_jack) \
    $(jack_check_timestamp) \
    $(built_dex)

# See comment in java.mk
ifndef LOCAL_CHECKED_MODULE
LOCAL_CHECKED_MODULE := $(jack_check_timestamp)
endif

#######################################
include $(BUILD_SYSTEM)/base_rules.mk
#######################################
java_sources := $(addprefix $(LOCAL_PATH)/, $(filter %.java,$(LOCAL_SRC_FILES))) \
                $(filter %.java,$(LOCAL_GENERATED_SOURCES))
all_java_sources := $(java_sources)

include $(BUILD_SYSTEM)/java_common.mk

$(cleantarget): PRIVATE_CLEAN_FILES += $(intermediates.COMMON)

$(LOCAL_INTERMEDIATE_TARGETS): \
  PRIVATE_JACK_INTERMEDIATES_DIR := $(intermediates.COMMON)/jack-rsc

ifeq ($(LOCAL_JACK_ENABLED),incremental)
$(LOCAL_INTERMEDIATE_TARGETS): \
  PRIVATE_JACK_INCREMENTAL_DIR := $(intermediates.COMMON)/jack-incremental
else
$(LOCAL_INTERMEDIATE_TARGETS): \
  PRIVATE_JACK_INCREMENTAL_DIR :=
endif
$(LOCAL_INTERMEDIATE_TARGETS): PRIVATE_JACK_FLAGS := $(GLOBAL_JAVAC_DEBUG_FLAGS) $(LOCAL_JACK_FLAGS)
$(LOCAL_INTERMEDIATE_TARGETS): PRIVATE_JACK_VERSION_LEVEL := $(LOCAL_JACK_VERSION_LEVEL)
$(LOCAL_INTERMEDIATE_TARGETS): PRIVATE_JACK_MIN_SDK_VERSION := $(PLATFORM_JACK_MIN_SDK_VERSION)

jack_all_deps := $(java_sources) $(java_resource_sources) $(full_jack_deps) \
        $(jar_manifest_file) $(proto_java_sources_file_stamp) \
        $(LOCAL_ADDITIONAL_DEPENDENCIES) $(NORMALIZE_PATH) $(JACK)

ifneq ($(LOCAL_IS_STATIC_JAVA_LIBRARY),true)
$(built_dex): PRIVATE_CLASSES_JACK := $(full_classes_jack)
$(built_dex): $(jack_all_deps) | setup-jack-server
	@echo Building with Jack: $@
	$(jack-java-to-dex)

# $(full_classes_jack) is just by-product of $(built_dex).
# The dummy command was added because, without it, make misses the fact the $(built_dex) also
# change $(full_classes_jack).
$(full_classes_jack): $(built_dex)
	$(hide) touch $@

$(LOCAL_BUILT_MODULE): PRIVATE_DEX_FILE := $(built_dex)
$(LOCAL_BUILT_MODULE): $(built_dex) $(java_resource_sources)
	@echo "Host Jar: $(PRIVATE_MODULE) ($@)"
	$(create-empty-package)
	$(add-dex-to-package)
	$(add-carried-jack-resources)

else  # LOCAL_IS_STATIC_JAVA_LIBRARY
$(full_classes_jack): $(jack_all_deps) | setup-jack-server
	@echo Building with Jack: $@
	$(java-to-jack)

endif  # LOCAL_IS_STATIC_JAVA_LIBRARY

$(jack_check_timestamp): $(jack_all_deps) | setup-jack-server
	@echo Checking build with Jack: $@
	$(jack-check-java)

USE_CORE_LIB_BOOTCLASSPATH :=

endif
