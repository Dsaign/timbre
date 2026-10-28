// Dev only: log once at server start whether back answers with our token.
export async function register() {
  if (
    process.env.NODE_ENV !== 'development' ||
    process.env.NEXT_RUNTIME !== 'nodejs'
  )
    return
  const { back } = await import('@/lib/api/client')
  try {
    const { data, response } = await back.GET('/health')
    console.log(
      `[timbre] back /health → ${response.status} ${data?.status ?? ''}`
    )
  } catch {
    console.log(`[timbre] back unreachable at ${process.env.BACK_URL}`)
  }
}
