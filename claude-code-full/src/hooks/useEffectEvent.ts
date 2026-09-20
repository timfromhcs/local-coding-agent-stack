import * as React from 'react';

/**
 * Polyfill for React's experimental useEffectEvent hook.
 * Returns a stable function identity that always calls the latest callback
 * without depending on resolveDispatcher().useEffectEvent.
 */
export function useEffectEvent<T extends (...args: any[]) => any>(fn: T): T {
  const ref = React.useRef<T>(fn);
  ref.current = fn;
  return React.useCallback(((...args: any[]) => ref.current(...args)) as T, []);
}

export default useEffectEvent;
