###########################################################
## Clear out values of all variables used by rule templates.
###########################################################

LOCAL_MODULE:=
LOCAL_MODULE_PATH:=
LOCAL_MODULE_STEM:=
LOCAL_DONT_CHECK_MODULE:=
LOCAL_CHECKED_MODULE:=
LOCAL_BUILT_MODULE:=
LOCAL_BUILT_MODULE_STEM:=
OVERRIDE_BUILT_MODULE_PATH:=
LOCAL_INSTALLED_MODULE:=
LOCAL_UNINSTALLABLE_MODULE:=
LOCAL_INTERMEDIATE_TARGETS:=
LOCAL_UNSTRIPPED_PATH:=
LOCAL_MODULE_CLASS:=
LOCAL_MODULE_SUFFIX:=
LOCAL_PACKAGE_NAME:=
LOCAL_OVERRIDES_PACKAGES:=
LOCAL_EXPORT_PACKAGE_RESOURCES:=
LOCAL_MANIFEST_PACKAGE_NAME:=
LOCAL_REQUIRED_MODULES:=
LOCAL_ACP_UNAVAILABLE:=
LOCAL_MODULE_TAGS:=
LOCAL_SRC_FILES:=
LOCAL_PREBUILT_OBJ_FILES:=
LOCAL_STATIC_JAVA_LIBRARIES:=
LOCAL_STATIC_LIBRARIES:=
# Group static libraries with "-Wl,--start-group" and "-Wl,--end-group" when linking.
LOCAL_GROUP_STATIC_LIBRARIES:=
LOCAL_WHOLE_STATIC_LIBRARIES:=
LOCAL_SHARED_LIBRARIES:=
LOCAL_IS_HOST_MODULE:=
LOCAL_CC:=
LOCAL_CXX:=
LOCAL_CPP_EXTENSION:=
LOCAL_NO_DEFAULT_COMPILER_FLAGS:=
LOCAL_NO_FDO_SUPPORT :=
LOCAL_ARCH_MODE:=
LOCAL_ARM_MODE:=
LOCAL_MIPS_MODE:=
LOCAL_YACCFLAGS:=
LOCAL_ASFLAGS:=
LOCAL_CFLAGS:=
LOCAL_CPPFLAGS:=
LOCAL_RTTI_FLAG:=
LOCAL_C_INCLUDES:=
LOCAL_LDFLAGS:=
LOCAL_LDLIBS:=
LOCAL_AAPT_FLAGS:=
LOCAL_AAPT_INCLUDE_ALL_RESOURCES:=
LOCAL_SYSTEM_SHARED_LIBRARIES:=none
LOCAL_PREBUILT_LIBS:=
LOCAL_PREBUILT_EXECUTABLES:=
LOCAL_PREBUILT_JAVA_LIBRARIES:=
LOCAL_PREBUILT_STATIC_JAVA_LIBRARIES:=
LOCAL_PREBUILT_STRIP_COMMENTS:=
LOCAL_INTERMEDIATE_SOURCES:=
LOCAL_INTERMEDIATE_SOURCE_DIR:=
LOCAL_JAVACFLAGS:=
LOCAL_JAVA_LIBRARIES:=
LOCAL_NO_STANDARD_LIBRARIES:=
LOCAL_CLASSPATH:=
LOCAL_DROIDDOC_USE_STANDARD_DOCLET:=
LOCAL_DROIDDOC_SOURCE_PATH:=
LOCAL_DROIDDOC_TEMPLATE_DIR:=
LOCAL_DROIDDOC_CUSTOM_TEMPLATE_DIR:=
LOCAL_DROIDDOC_ASSET_DIR:=
LOCAL_DROIDDOC_CUSTOM_ASSET_DIR:=
LOCAL_DROIDDOC_OPTIONS:=
LOCAL_DROIDDOC_HTML_DIR:=
LOCAL_ASSET_FILES:=
LOCAL_ASSET_DIR:=
LOCAL_RESOURCE_DIR:=
LOCAL_JAVA_RESOURCE_DIRS:=
LOCAL_JAVA_RESOURCE_FILES:=
LOCAL_GENERATED_SOURCES:=
LOCAL_COPY_HEADERS_TO:=
LOCAL_COPY_HEADERS:=
LOCAL_FORCE_STATIC_EXECUTABLE:=
LOCAL_ADDITIONAL_DEPENDENCIES:=
LOCAL_COMPRESS_MODULE_SYMBOLS:=
LOCAL_STRIP_MODULE:=
LOCAL_POST_PROCESS_COMMAND:=true
LOCAL_JNI_SHARED_LIBRARIES:=
LOCAL_JNI_SHARED_LIBRARIES_ABI:=
LOCAL_JAR_MANIFEST:=
LOCAL_INSTRUMENTATION_FOR:=
LOCAL_MANIFEST_INSTRUMENTATION_FOR:=
LOCAL_AIDL_INCLUDES:=
LOCAL_JARJAR_RULES:=
LOCAL_ADDITIONAL_JAVA_DIR:=
LOCAL_ALLOW_UNDEFINED_SYMBOLS:=
LOCAL_DX_FLAGS:=
LOCAL_CERTIFICATE:=
LOCAL_SDK_VERSION:=
LOCAL_SDK_RES_VERSION:=
LOCAL_NDK_VERSION:=
LOCAL_NDK_STL_VARIANT:=
LOCAL_NO_EMMA_INSTRUMENT:=
LOCAL_NO_EMMA_COMPILE:=
LOCAL_PROGUARD_ENABLED:= # '',optonly,full,custom,disabled
LOCAL_PROGUARD_FLAGS:=
LOCAL_PROGUARD_FLAG_FILES:=
LOCAL_EMMA_COVERAGE_FILTER:=
LOCAL_WARNINGS_ENABLE:=
LOCAL_MANIFEST_FILE:=
LOCAL_RENDERSCRIPT_INCLUDES:=
LOCAL_RENDERSCRIPT_INCLUDES_OVERRIDE:=
LOCAL_RENDERSCRIPT_CC:=
LOCAL_RENDERSCRIPT_TARGET_API:=
LOCAL_BUILD_HOST_DEX:=
LOCAL_DEX_PREOPT:= # '',true,false,nostripping
LOCAL_PROTOC_OPTIMIZE_TYPE:= # lite(default),micro,full
LOCAL_PROTOC_FLAGS:=
LOCAL_NO_CRT:=
LOCAL_PROPRIETARY_MODULE:=
LOCAL_CTS_TEST_PACKAGE:=

# Trim MAKEFILE_LIST so that $(call my-dir) doesn't need to
# iterate over thousands of entries every time.
# Leave the current makefile to make sure we don't break anything
# that expects to be able to find the name of the current makefile.
MAKEFILE_LIST := $(lastword $(MAKEFILE_LIST))
