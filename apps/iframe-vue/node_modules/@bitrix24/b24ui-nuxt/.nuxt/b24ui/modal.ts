const overlayBlur = [
  "auto",
  "on",
  "off"
] as const

export default {
  "slots": {
    "overlay": "fixed inset-0 bg-[#003366]/20",
    "content": "light bg-(--popup-window-background-color) fixed flex flex-col gap-[20px] focus:outline-none p-[24px] pt-[20px]",
    "contentWrapper": "flex flex-col gap-[15px] pt-[4px]",
    "header": "flex items-start justify-between gap-[6px]",
    "wrapper": "",
    "title": "font-[family-name:var(--ui-font-family-primary)] text-(--b24ui-typography-label-color) font-(--ui-font-weight-medium) mb-0 text-[calc(var(--ui-font-size-2xl)+2px)]/(--ui-font-size-2xl)",
    "description": "mt-1 text-(--b24ui-typography-description-color) text-(length:--ui-font-size-sm)",
    "close": "-mt-[4px]",
    "body": "flex-1 overflow-y-auto text-(length:--ui-font-size-md) leading-normal",
    "footer": "flex items-center justify-between gap-[10px] border-t border-t-1 border-t-(--ui-color-divider-default) pt-[18px]"
  },
  "variants": {
    "overlayBlur": {
      "auto": {
        "overlay": "motion-safe:backdrop-blur-[2px]"
      },
      "on": {
        "overlay": "backdrop-blur-[2px]"
      },
      "off": {
        "overlay": ""
      }
    },
    "transition": {
      "true": {
        "overlay": "motion-safe:data-[state=open]:animate-[fade-in_200ms_ease-out] motion-safe:data-[state=closed]:animate-[fade-out_200ms_ease-in]",
        "content": "motion-safe:data-[state=open]:animate-[scale-in_200ms_ease-out] motion-safe:data-[state=closed]:animate-[scale-out_200ms_ease-in]"
      }
    },
    "fullscreen": {
      "true": {
        "content": "inset-0"
      },
      "false": {
        "content": "top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[calc(100vw-2rem)] max-w-[32rem] max-h-[calc(100dvh-2rem)] sm:max-h-[calc(100dvh-4rem)] rounded-[calc(var(--popup-window-border-radius)-2px)] shadow-lg",
        "contentWrapper": "overflow-hidden"
      }
    },
    "scrollbarThin": {
      "true": {
        "body": "scrollbar-thin"
      }
    }
  },
  "defaultVariants": {
    "scrollbarThin": true,
    "overlayBlur": "auto" as typeof overlayBlur[number]
  }
}