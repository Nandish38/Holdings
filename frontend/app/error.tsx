"use client";

export default function AppError({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return (
    <div className="errorShell">
      <h1>Something went wrong</h1>
      <p className="muted">
        This page could not load. Often this means the server cannot reach the API. Check Vercel{" "}
        <code>API_BASE_URL</code> and that Render allows your Vercel origin in <code>CORS_ALLOW_ORIGINS</code>.
      </p>
      <pre className="errorDetail">{error.message}</pre>
      <button type="button" className="retryBtn" onClick={() => reset()}>
        Try again
      </button>
    </div>
  );
}
