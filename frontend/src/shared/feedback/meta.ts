/** What each action says about itself, read by the one handler in App.tsx that turns results into messages. */
// A type, not an interface: the query library wants a record shape for its meta.
export type ActionMeta = {
  /** Shown when it worked, e.g. "Reply sent". Leave it out where the screen itself shows the change. */
  success?: string;
  /** The action's name for an error title, e.g. "The reply" did not go through. */
  action?: string;
  /** The component shows this error itself (a form field, a sign in page); no message is raised. */
  quiet?: boolean;
};

declare module '@tanstack/react-query' {
  interface Register {
    mutationMeta: ActionMeta;
  }
}
