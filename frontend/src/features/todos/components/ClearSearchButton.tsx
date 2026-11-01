import { Button } from '../../../design-system'

export function ClearSearchButton({
  search,
  onClear,
}: {
  search: string
  onClear: () => void
}) {
  return (
    <Button variant="secondary" disabled={!search.trim()} onClick={onClear}>
      Clear search
    </Button>
  )
}
