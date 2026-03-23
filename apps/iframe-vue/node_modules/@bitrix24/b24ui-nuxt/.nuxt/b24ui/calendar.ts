const color = [
  "air-primary",
  "air-primary-success",
  "air-primary-alert",
  "air-primary-copilot",
  "air-primary-warning",
  "default",
  "danger",
  "success",
  "warning",
  "primary",
  "secondary",
  "collab",
  "ai"
] as const

const size = [
  "xs",
  "sm",
  "md",
  "lg"
] as const

export default {
  "slots": {
    "root": "font-[family-name:var(--ui-font-family-primary)] w-full",
    "header": "flex items-center justify-between",
    "body": "flex flex-col space-y-4 pt-4 sm:flex-row sm:space-x-4 sm:space-y-0",
    "heading": "mx-auto text-center font-(--ui-font-weight-semibold) truncate",
    "grid": "w-full border-collapse select-none space-y-1 focus:outline-none",
    "gridRow": "grid grid-cols-7 place-items-center",
    "gridWeekDaysRow": "mb-1 grid w-full grid-cols-7",
    "gridBody": "grid",
    "headCell": "font-(--ui-font-weight-normal) text-(--ui-color-design-plain-na-content)",
    "cell": "relative text-center cursor-pointer aria-disabled:cursor-not-allowed",
    "cellTrigger": "m-0.5 relative flex items-center justify-center rounded-full whitespace-nowrap focus-visible:ring-2 focus:outline-none text-(--b24ui-typography-label-color) data-disabled:text-(--b24ui-typography-legend-color) data-unavailable:text-(--b24ui-typography-legend-color) data-outside-view:text-(--ui-color-design-plain-na-content-secondary) data-[selected]:text-(--b24ui-color) focus-visible:ring-(--b24ui-background-hover) data-[selected]:bg-(--b24ui-background) data-today:not-data-[selected]:text-(--b24ui-background) data-[highlighted]:bg-(--b24ui-background) data-[highlighted]:text-(--b24ui-color) hover:not-data-[disabled]:not-data-[selected]:bg-(--b24ui-background) hover:not-data-[disabled]:not-data-[selected]:text-(--b24ui-color) data-unavailable:line-through data-unavailable:pointer-events-none data-today:font-(--ui-font-weight-semibold) transition"
  },
  "variants": {
    "color": {
      "air-primary": {
        "root": "style-filled"
      },
      "air-primary-success": {
        "root": "style-filled-success"
      },
      "air-primary-alert": {
        "root": "style-filled-alert"
      },
      "air-primary-copilot": {
        "root": "style-filled-copilot"
      },
      "air-primary-warning": {
        "root": "style-filled-warning"
      },
      "default": {
        "root": "style-old-default"
      },
      "danger": {
        "root": "style-old-danger"
      },
      "success": {
        "root": "style-old-success"
      },
      "warning": {
        "root": "style-old-warning"
      },
      "primary": {
        "root": "style-old-primary"
      },
      "secondary": {
        "root": "style-old-secondary"
      },
      "collab": {
        "root": "style-old-collab"
      },
      "ai": {
        "root": "style-old-ai"
      }
    },
    "size": {
      "xs": {
        "heading": "text-(length:--ui-font-size-md)",
        "cell": "text-(length:--ui-font-size-sm)",
        "headCell": "text-[10px]",
        "cellTrigger": "size-[28px]",
        "body": "space-y-2 pt-2"
      },
      "sm": {
        "heading": "text-(length:--ui-font-size-md)",
        "headCell": "text-(length:--ui-font-size-sm)",
        "cell": "text-(length:--ui-font-size-sm)",
        "cellTrigger": "size-[28px]"
      },
      "md": {
        "heading": "text-(length:--ui-font-size-lg)",
        "headCell": "text-(length:--ui-font-size-md)",
        "cell": "text-(length:--ui-font-size-md)",
        "cellTrigger": "size-[32px]"
      },
      "lg": {
        "heading": "text-(length:--ui-font-size-2xl)",
        "headCell": "text-(length:--ui-font-size-lg)",
        "cell": "text-(length:--ui-font-size-lg)",
        "cellTrigger": "size-[36px] text-(length:--ui-font-size-lg)"
      }
    }
  },
  "defaultVariants": {
    "size": "md" as typeof size[number],
    "color": "air-primary" as typeof color[number]
  }
}