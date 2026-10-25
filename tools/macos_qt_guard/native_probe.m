#import <Foundation/Foundation.h>
#import <objc/runtime.h>
#import <objc/message.h>
#include <stdint.h>
__attribute__((visibility("default"))) int qt_guard_probe(uint32_t tableId, unsigned long *selectedCount, unsigned long *cellRoles) {
    Class cls = objc_getClass("QMacAccessibilityElement");
    id table = ((id (*)(id,SEL,uint32_t))objc_msgSend)(cls,sel_registerName("elementWithId:"),tableId);
    if (!table) return -1;
    NSArray *rows = ((id (*)(id,SEL))objc_msgSend)(table,sel_registerName("accessibilityRows"));
    for (id row in rows) ((id (*)(id,SEL))objc_msgSend)(row,sel_registerName("accessibilityChildren"));
    NSArray *selected = ((id (*)(id,SEL))objc_msgSend)(table,sel_registerName("accessibilitySelectedChildren"));
    *selectedCount = selected.count;
    *cellRoles = 0;
    for(id cell in selected) {
        id role=((id (*)(id,SEL))objc_msgSend)(cell,sel_registerName("accessibilityRole"));
        if ([role isEqualToString:@"AXCell"]) (*cellRoles)++;
    }
    return 0;
}
