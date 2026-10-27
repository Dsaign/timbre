import { Field, FieldLabel } from '@/components/ui/field'
import { JSX } from 'react'

type Props = {
  width: string
  children: JSX.Element
  label?: string
}

export default function SearchBox(props: Props) {
  return (
    <div className="flex-row items-center">
      <Field className="flex-col" style={{ width: props.width }}>
        {props.label && (
          <FieldLabel htmlFor="input-seach">{props.label}</FieldLabel>
        )}
        {props.children}
      </Field>
    </div>
  )
}
