import { fmtTime } from '@/utils/time'

/** 表格空值占位（与业务约定：数值 0 仍正常展示） */
export const TABLE_EMPTY_PLACEHOLDER = '--'

export function isTableCellEmpty(value: unknown): boolean {
  if (value === null || value === undefined) return true
  if (typeof value === 'string' && value.trim() === '') return true
  if (typeof value === 'number' && Number.isNaN(value)) return true
  return false
}

/** 文本/数字单元格：空 → `--`，`0` 显示为 `0` */
export function tableCellDisplay(value: unknown): string {
  if (isTableCellEmpty(value)) return TABLE_EMPTY_PLACEHOLDER
  return String(value as string | number | bigint | boolean)
}

/** Element Plus `el-table-column` 的 formatter */
export function tableTextFormatter(_row: unknown, _column: unknown, cellValue: unknown) {
  return tableCellDisplay(cellValue)
}

/** 时间列：空 → `--`，否则走统一时间格式化 */
export function tableCellDisplayTime(value: unknown): string {
  if (isTableCellEmpty(value)) return TABLE_EMPTY_PLACEHOLDER
  return fmtTime(String(value))
}
