export default {
  "slots": {
    "root": "sidebar-layout text-(--b24ui-typography-label-color) w-full flex",
    "sidebar": "air-sidebar before:absolute before:inset-0 before:z-[-1] before:bg-(--leftmenu-bg-expanded) w-[240px] pe-[3px] rtl:me-[14px] inset-y-0 left-0 max-lg:hidden",
    "sidebarSlideoverContainer": "w-full sm:max-w-80",
    "sidebarSlideover": "h-full overflow-hidden flex flex-col text-(--b24ui-typography-label-color) bg-(--ui-color-base-white-fixed) dark:bg-(--ui-color-bg-content-primary) edge-dark:bg-[#21334cf0] ring-1 ring-(--ui-color-divider-vibrant-less) shadow-xs rounded-none",
    "sidebarSlideoverBtnClose": "-mb-3 px-4 pt-3",
    "contentWrapper": "flex-1 flex flex-col ",
    "header": "air-header px-(--content-area-shift) min-h-(--topbar-height) flex items-center gap-x-1",
    "headerMenuIcon": "lg:hidden",
    "headerWrapper": "min-w-0 flex-1 h-full",
    "container": "flex-1 flex flex-col gap-[22px] lg:min-w-0",
    "containerWrapper": "grow group/layout-content",
    "pageTopWrapper": "text-(--ui-color-base-1) flex items-center gap-[12px]",
    "pageActionsWrapper": "flex flex-col md:flex-row items-start md:items-center justify-start gap-[12px]",
    "containerWrapperInner": "size-full",
    "pageBottomWrapper": "",
    "loadingWrapper": "cursor-wait isolate absolute z-1000 inset-0 w-full h-dvh flex flex-row flex-nowrap items-center justify-center",
    "loadingIcon": "text-(--ui-color-design-plain-content-icon-secondary) size-[110px] animate-spin-slow"
  },
  "variants": {
    "inner": {
      "true": {
        "root": "--inner light relative isolate h-full overflow-hidden",
        "sidebar": "relative z-[0]",
        "header": "relative",
        "container": "mt-0",
        "containerWrapper": "",
        "pageBottomWrapper": "flex-0"
      },
      "false": {
        "root": "--app h-screen min-h-screen max-lg:flex-col",
        "sidebar": "fixed",
        "header": "relative",
        "container": "relative mt-[22px]"
      }
    },
    "offContentScrollbar": {
      "false": "",
      "true": ""
    },
    "useSidebar": {
      "true": "",
      "false": ""
    },
    "useLightContent": {
      "true": {
        "containerWrapper": "light text-(--ui-color-text-primary) bg-(--ui-color-bg-content-primary) ",
        "loadingIcon": "edge-dark:text-(--ui-color-gray-70)"
      },
      "false": {
        "container": "px-(--content-area-shift)"
      }
    },
    "loading": {
      "true": ""
    },
    "useNavbar": {
      "true": {
        "container": ""
      },
      "false": {
        "loadingWrapper": "h-full",
        "container": ""
      }
    }
  },
  "compoundVariants": [
    {
      "inner": true,
      "useLightContent": true,
      "class": {
        "container": "",
        "pageTopWrapper": "px-0 lg:px-0",
        "pageActionsWrapper": "px-0 lg:px-0",
        "containerWrapper": "p-[20px] rounded-(--ui-border-radius-md)"
      }
    },
    {
      "inner": false,
      "useLightContent": true,
      "class": {
        "container": "lg:pb-2",
        "pageTopWrapper": "px-6 lg:px-0",
        "pageActionsWrapper": "px-6 lg:px-0",
        "containerWrapper": "p-6 lg:px-[22px] lg:py-[15px] lg:rounded-(--ui-border-radius-md)"
      }
    },
    {
      "inner": true,
      "offContentScrollbar": false,
      "class": {
        "container": "scrollbar-thin scrollbar-transparent overflow-y-scroll"
      }
    },
    {
      "inner": true,
      "useSidebar": [
        true,
        false
      ],
      "class": {
        "container": "px-[20px] ps-[20px] pe-[10px] pb-[20px] lg:pt-0 lg:px-[20px] lg:ps-[20px] lg:pe-[10px]"
      }
    },
    {
      "inner": false,
      "useSidebar": true,
      "class": {
        "container": "lg:px-(--content-area-shift)",
        "contentWrapper": "lg:pl-[240px] "
      }
    },
    {
      "inner": false,
      "useSidebar": false,
      "class": {
        "container": "px-(--content-area-shift) pb-2 lg:pt-2 lg:px-2",
        "contentWrapper": "lg:pl-0"
      }
    },
    {
      "inner": true,
      "useNavbar": [
        true,
        false
      ],
      "class": {
        "container": "h-full"
      }
    },
    {
      "inner": false,
      "useNavbar": true,
      "class": {
        "container": "h-[calc(100dvh-var(--topbar-height))]"
      }
    },
    {
      "inner": false,
      "useNavbar": false,
      "class": {
        "container": "h-full"
      }
    }
  ],
  "defaultVariants": {
    "inner": false,
    "noContentScrollbar": false,
    "useLightContent": true
  }
}