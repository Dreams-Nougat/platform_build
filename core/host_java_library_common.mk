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
# Common rules for building a host java library.
#

LOCAL_MODULE_CLASS := JAVA_LIBRARIES
LOCAL_MODULE_SUFFIX := $(COMMON_JAVA_PACKAGE_SUFFIX)
LOCAL_IS_HOST_MODULE := true
LOCAL_BUILT_MODULE_STEM := javalib.jar

intermediates := $(call local-intermediates-dir)
intermediates.COMMON := $(call local-intermediates-dir,COMMON)

built_javalib_jar := $(intermediates)/javalib.jar

#################################
include $(BUILD_SYSTEM)/configure_local_jack.mk
#################################

ifdef LOCAL_JACK_ENABLED
ifdef LOCAL_IS_STATIC_JAVA_LIBRARY
LOCAL_BUILT_MODULE_STEM := classes.jack
LOCAL_INTERMEDIATE_TARGETS += $(built_javalib_jar)
endif
endif

# base_rules.mk looks at this
all_res_assets :=

proto_sources := $(filter %.proto,$(LOCAL_SRC_FILES))
ifneq ($(proto_sources),)
ifeq ($(LOCAL_PROTOC_OPTIMIZE_TYPE),micro)
    LOCAL_JAVA_LIBRARIES += host-libprotobuf-java-micro
else
  ifeq ($(LOCAL_PROTOC_OPTIMIZE_TYPE),nano)
    LOCAL_JAVA_LIBRARIES += host-libprotobuf-java-nano
  else
    LOCAL_JAVA_LIBRARIES += host-libprotobuf-java-lite
  endif
endif
endif

LOCAL_INTERMEDIATE_SOURCE_DIR := $(intermediates.COMMON)/src
LOCAL_JAVA_LIBRARIES := $(sort $(LOCAL_JAVA_LIBRARIES))

