const angle = [
  "top",
  "bottom"
] as const

export default {
  "slots": {
    "root": "light style-outline-accent-1 flex items-end",
    "descriptionWrapper": "relative",
    "descriptionBorder": "fill-(--b24ui-border-color)",
    "descriptionBg": "fill-(--b24ui-background) dark:fill-(--ui-color-base-6)",
    "descriptionAngle": "absolute w-[14px] h-[12px]",
    "description": "grow w-11/12 py-3 px-md2 ms-2 rounded-[23px] font-[family-name:var(--ui-font-family-secondary)] text-(length:--ui-font-size-md)/(--ui-font-line-height-md) font-(--ui-font-weight-normal) border-1 border-(--b24ui-border-color) bg-(--b24ui-background) text-(--b24ui-color) dark:bg-(--ui-color-base-6)",
    "leading": "me-1.5 ms-2 font-(--ui-font-weight-medium) text-(--ui-color-design-plain-content-icon-secondary)",
    "leadingIcon": "shrink-0 size-[42px]",
    "leadingAvatar": "shrink-0",
    "leadingAvatarIcon": "text-(--b24ui-typography-label-color) bg-(--ui-color-base-8)",
    "leadingAvatarSize": "lg"
  },
  "variants": {
    "angle": {
      "top": {
        "root": "items-start",
        "leading": "mt-0.5",
        "descriptionAngle": "start-[0.8px] top-[9px] scale-x-100 -scale-y-100 rtl:-scale-x-100"
      },
      "bottom": {
        "root": "items-end",
        "descriptionAngle": "start-[0.8px] bottom-[9px] rtl:-scale-x-100"
      }
    }
  },
  "defaultVariants": {
    "angle": "bottom" as typeof angle[number]
  }
}