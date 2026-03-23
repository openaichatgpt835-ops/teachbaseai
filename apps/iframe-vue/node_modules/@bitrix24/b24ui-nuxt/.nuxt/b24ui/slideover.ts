const overlayBlur = [
  "auto",
  "on",
  "off"
] as const

const side = [
  "right",
  "left",
  "top",
  "bottom"
] as const

export default {
  "slots": {
    "overlay": "fixed inset-0 bg-linear-to-b from-[#00204e]/52 to-[#00204e]",
    "content": "fixed sm:shadow-lg flex flex-col focus:outline-none h-full",
    "sidebarLayoutRoot": "",
    "sidebarLayoutHeaderWrapper": "",
    "sidebarLayoutPageBottomWrapper": "",
    "sidebarLayoutLoadingWrapper": "",
    "sidebarLayoutLoadingIcon": "",
    "header": "pt-[24px] flex-1 flex items-center gap-x-[12px] gap-y-1.5",
    "wrapper": "min-h-[30px]",
    "title": "font-[family-name:var(--ui-font-family-primary)] text-(--b24ui-typography-label-color) font-(--ui-font-weight-semi-bold) mb-0 text-(length:--ui-font-size-4xl)/[calc(var(--ui-font-size-4xl)+2px)]",
    "description": "mt-1 text-(--b24ui-typography-description-color) text-(length:--ui-font-size-sm)",
    "close": "absolute",
    "body": "size-full flex-1",
    "footer": "light bg-(--popup-window-background-color) flex items-center justify-center gap-3 border-t border-t-1 border-t-(--ui-color-divider-less) shadow-top-md py-[9px] px-2 pr-(--scrollbar-width)",
    "safeList": "group-hover:rounded-full group-hover:border-1 group-hover:border-current"
  },
  "variants": {
    "overlayBlur": {
      "auto": {
        "overlay": "motion-safe:backdrop-blur-sm"
      },
      "on": {
        "overlay": "backdrop-blur-sm"
      },
      "off": {
        "overlay": ""
      }
    },
    "side": {
      "right": {
        "content": "right-0 inset-y-0 w-[calc(100%-60px)] sm:w-[calc(100%-150px)]",
        "sidebarLayoutRoot": "sm:rounded-t-none"
      },
      "left": {
        "content": "left-0 inset-y-0 w-[calc(100%-60px)] sm:w-[calc(100%-150px)]",
        "sidebarLayoutRoot": "sm:rounded-t-none"
      },
      "top": {
        "content": "inset-x-0 top-0 max-h-full",
        "sidebarLayoutRoot": "sm:rounded-t-none"
      },
      "bottom": {
        "content": "right-[5px] sm:right-[70px] top-0 sm:top-[18px] bottom-0 w-[calc(100%-60px-5px)] sm:w-[calc(100%-150px-70px)] sm:max-h-[calc(100%-18px)]",
        "sidebarLayoutRoot": "sm:rounded-t-[18px]"
      }
    },
    "transition": {
      "true": {
        "overlay": "motion-safe:data-[state=open]:animate-[fade-in_200ms_ease-out] motion-safe:data-[state=closed]:animate-[fade-out_200ms_ease-in]"
      }
    }
  },
  "compoundVariants": [
    {
      "side": [
        "right" as typeof side[number],
        "bottom" as typeof side[number]
      ],
      "class": {
        "close": "pl-1.5 pr-[4px] top-[17px] -translate-x-full left-[1px] rounded-l-full"
      }
    },
    {
      "side": "left" as typeof side[number],
      "class": {
        "close": "pr-1.5 pl-[4px] top-[17px] translate-x-full right-[1px] rounded-r-full [&>div]:flex-row-reverse"
      }
    },
    {
      "side": "top" as typeof side[number],
      "class": {
        "close": "top-4 end-4"
      }
    },
    {
      "transition": true,
      "side": "top" as typeof side[number],
      "class": {
        "content": "motion-safe:data-[state=open]:animate-[slide-in-from-top_200ms_ease-in-out] motion-safe:data-[state=closed]:animate-[slide-out-to-top_200ms_ease-in-out]"
      }
    },
    {
      "transition": true,
      "side": "right" as typeof side[number],
      "class": {
        "content": "motion-safe:data-[state=open]:animate-[slide-in-from-right_200ms_ease-in-out] motion-safe:data-[state=closed]:animate-[slide-out-to-right_200ms_ease-in-out]"
      }
    },
    {
      "transition": true,
      "side": "bottom" as typeof side[number],
      "class": {
        "content": "motion-safe:data-[state=open]:animate-[slide-in-from-bottom_200ms_ease-in-out] motion-safe:data-[state=closed]:animate-[slide-out-to-bottom_200ms_ease-in-out]"
      }
    },
    {
      "transition": true,
      "side": "left" as typeof side[number],
      "class": {
        "content": "motion-safe:data-[state=open]:animate-[slide-in-from-left_200ms_ease-in-out] motion-safe:data-[state=closed]:animate-[slide-out-to-left_200ms_ease-in-out]"
      }
    }
  ],
  "defaultVariants": {
    "side": "bottom" as typeof side[number],
    "overlayBlur": "off" as typeof overlayBlur[number]
  }
}