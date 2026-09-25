/**
 * Error boundary for the R3F scenes.
 *
 * `useLoader` throws when a texture cannot be fetched. Without a boundary that
 * throw propagates all the way out and React unmounts the whole tree — a blank
 * page, with the intro gate's scroll lock still applied. That is the failure
 * mode if someone clones the repo and skips `scripts/prepare_assets.py`.
 *
 * With this in place the textured globe simply drops out and the rest of the
 * hero (the point-cloud Earth, the line art, every section below) keeps working.
 */
import { Component, type ErrorInfo, type ReactNode } from "react"

interface Props {
  children: ReactNode
  /** Rendered in place of the children after a failure. */
  fallback?: ReactNode
  label?: string
}

interface State {
  failed: boolean
}

export class SceneErrorBoundary extends Component<Props, State> {
  state: State = { failed: false }

  static getDerivedStateFromError(): State {
    return { failed: true }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    // Surface it once, but never let it take the page down.
    console.warn(
      `[${this.props.label ?? "scene"}] disabled after an error:`,
      error.message,
      info.componentStack
    )
  }

  render() {
    if (this.state.failed) return this.props.fallback ?? null
    return this.props.children
  }
}
