PRODUCT_PROPERTY_OVERRIDES :=

PRODUCT_PACKAGES := \
	AlarmClock \
	ApiDemos \
	Camera \
	Development \
	DrmProvider \
	Email \
	Fallback \
	GPSEnable \
	Launcher \
	Maps \
	Music \
	Mms \
	Settings \
	SdkSetup \
	gpstest \
	sqlite3


$(call inherit-product, $(SRC_TARGET_DIR)/product/core.mk)

# Overrides
PRODUCT_BRAND := generic
PRODUCT_NAME := sdk
PRODUCT_DEVICE := generic
