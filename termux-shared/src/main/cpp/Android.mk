LOCAL_PATH:= $(call my-dir)

include $(CLEAR_VARS)
LOCAL_LDLIBS := -llog
LOCAL_MODULE := local-socket
LOCAL_SRC_FILES := local-socket.cpp
include $(BUILD_SHARED_LIBRARY)

include $(CLEAR_VARS)
LOCAL_LDLIBS := -ldl -llog
LOCAL_MODULE := termex-redirect
LOCAL_SRC_FILES := termex-redirect.c
include $(BUILD_SHARED_LIBRARY)

