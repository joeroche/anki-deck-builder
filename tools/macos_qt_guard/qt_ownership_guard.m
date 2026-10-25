// Local backport of Qt Gerrit 765434's synthesized-element ownership guards.
// Does not suppress accessibility data or change QAccessible table semantics.
#import <Foundation/Foundation.h>
#import <objc/runtime.h>
#import <objc/message.h>
#include <stdint.h>
#include <stddef.h>
#include <string.h>
#include <dlfcn.h>
static IMP priorRemove;
static Ivar rowsIvar, columnsIvar;
static Class parentClass;
static void *(*cacheInstance)(void);
static void (*deleteInterface)(void *, uint32_t, void *);
static ptrdiff_t axidOffset;
static SEL managedSelector;
static unsigned long filteredCount, deallocCount;
static BOOL isParentManaged(id object) {
    return ((BOOL (*)(id, SEL))objc_msgSend)(object, managedSelector);
}
static void guardedRemove(id cls, SEL command, NSArray *array) {
    NSMutableArray *owned = [[NSMutableArray alloc] initWithCapacity:array.count];
    for (id cell in array) {
        if (!isParentManaged(cell)) [owned addObject:cell];
        else filteredCount++;
    }
    ((void (*)(id, SEL, NSArray *))priorRemove)(cls, command, owned);
    [owned release];
}
static void guardedDealloc(id self, SEL command) {
    // Faithful Qt destructor with the upstream ownership guard: no cache
    // lookup or deletion at all for a synthesized parent-managed element.
    id rows = object_getIvar(self, rowsIvar);
    id columns = object_getIvar(self, columnsIvar);
    Class cls = object_getClass(self);
    SEL remove = sel_registerName("removeElementsFromCache:");
    if (rows) {
        ((void (*)(id, SEL, id))objc_msgSend)(cls, remove, rows);
        [rows release];
    }
    if (columns) {
        ((void (*)(id, SEL, id))objc_msgSend)(cls, remove, columns);
        [columns release];
    }
    uint32_t axid = *(uint32_t *)((char *)self + axidOffset);
    if (axid && !isParentManaged(self)) deleteInterface(cacheInstance(), axid, NULL);
    else if (axid) deallocCount++;
    struct objc_super superclass = {self, parentClass};
    ((void (*)(struct objc_super *, SEL))objc_msgSendSuper)(&superclass, command);
}
__attribute__((visibility("default"))) const char *qt_guard_target_image(void) {
    Class cls = objc_getClass("QMacAccessibilityElement");
    return cls ? class_getImageName(cls) : NULL;
}
__attribute__((visibility("default"))) int install_qt_ownership_guard(void) {
    static BOOL installed = NO;
    if (installed) return 1;
    if (![NSThread isMainThread]) return -6;
    Class cls = objc_getClass("QMacAccessibilityElement");
    if (!cls) return -1;
    Ivar ivar = class_getInstanceVariable(cls, "axid");
    if (!ivar || strcmp(ivar_getTypeEncoding(ivar), "I")) return -2;
    managedSelector = sel_registerName("isManagedByParent");
    Method managed = class_getInstanceMethod(cls, managedSelector);
    Method remove = class_getClassMethod(cls, sel_registerName("removeElementsFromCache:"));
    Method dealloc = class_getInstanceMethod(cls, sel_registerName("dealloc"));
    if (!managed || !remove || !dealloc) return -3;
    rowsIvar = class_getInstanceVariable(cls, "rows");
    columnsIvar = class_getInstanceVariable(cls, "columns");
    if (!rowsIvar || !columnsIvar || ivar_getTypeEncoding(rowsIvar)[0] != '@' || ivar_getTypeEncoding(columnsIvar)[0] != '@') return -10;
    parentClass = class_getSuperclass(cls);
    if (!parentClass) return -11;
    cacheInstance = dlsym(RTLD_DEFAULT, "_ZN16QAccessibleCache8instanceEv");
    deleteInterface = dlsym(RTLD_DEFAULT, "_ZN16QAccessibleCache15deleteInterfaceEjP7QObject");
    if (!cacheInstance || !deleteInterface) return -12;
    if (method_getNumberOfArguments(managed) != 2 || method_getNumberOfArguments(remove) != 3 || method_getNumberOfArguments(dealloc) != 2) return -4;
    char result[16] = {0}, argument[16] = {0};
    method_getReturnType(remove, result, sizeof(result));
    method_getArgumentType(remove, 2, argument, sizeof(argument));
    if (strcmp(result, "v") || strcmp(argument, "@")) return -7;
    method_getReturnType(dealloc, result, sizeof(result));
    if (strcmp(result, "v")) return -8;
    method_getReturnType(managed, result, sizeof(result));
    if (strcmp(result, @encode(BOOL))) return -9;
    axidOffset = ivar_getOffset(ivar);
    if (axidOffset < (ptrdiff_t)sizeof(void *) || axidOffset + sizeof(uint32_t) > class_getInstanceSize(cls)) return -5;
    priorRemove = method_setImplementation(remove, (IMP)guardedRemove);
    method_setImplementation(dealloc, (IMP)guardedDealloc);
    installed = YES;
    return 0;
}
__attribute__((visibility("default"))) unsigned long qt_guard_filtered_count(void) { return filteredCount; }
__attribute__((visibility("default"))) unsigned long qt_guard_dealloc_count(void) { return deallocCount; }
