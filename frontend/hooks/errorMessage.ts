/**
 * 예외를 화면에 띄울 문자열로 바꾼다.
 *
 * `lib/api.ts`의 `request()`가 백엔드 오류를 이미 사람이 읽을 문장으로 만들어
 * `Error`에 담아 던지므로, 대개는 그 message를 그대로 쓰면 된다. fallback은
 * Error가 아닌 것이 던져진 경우에만 쓰인다.
 */
export function errorMessage(error: unknown, fallback: string): string {
  return error instanceof Error ? error.message : fallback;
}
