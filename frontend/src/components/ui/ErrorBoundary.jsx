import React from 'react';
import { AlertTriangle, RefreshCw } from 'lucide-react';

/**
 * Route-level crash barrier. A single panel whose canvas throws (e.g. the
 * force-graph) should not take down the shell — this boundary catches it,
 * shows a recoverable fallback, and lets the user retry without a full reload.
 */
export default class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, info) {
    // Kept intentionally terse — production telemetry is out of scope here.
    console.error('[NASO ErrorBoundary]', this.props.label ?? 'unknown', error, info);
  }

  reset = () => this.setState({ hasError: false, error: null });

  render() {
    if (!this.state.hasError) return this.props.children;

    const label = this.props.label ?? 'view';
    const message = this.state.error?.message ?? 'An unexpected render error occurred.';

    return (
      <div className="flex flex-col items-center justify-center gap-5 min-h-[320px] p-8 rounded-2xl border border-[#FF453A]/20 bg-[#FF453A]/[0.04]">
        <div className="p-3 rounded-2xl bg-[#FF453A]/10 border border-[#FF453A]/20">
          <AlertTriangle size={24} className="text-[#FF453A]" strokeWidth={1.5} />
        </div>
        <div className="text-center space-y-1">
          <p className="text-[14px] font-semibold text-white tracking-tight">
            {label} crashed during render
          </p>
          <p className="text-[12px] text-zinc-500 max-w-md">
            {message}
          </p>
        </div>
        <button
          onClick={this.reset}
          className="inline-flex items-center gap-2 h-9 px-5 rounded-full text-[13px] font-medium bg-[#0A84FF] hover:bg-[#007AFF] text-white transition-colors"
        >
          <RefreshCw size={14} strokeWidth={2} />
          Retry
        </button>
      </div>
    );
  }
}
