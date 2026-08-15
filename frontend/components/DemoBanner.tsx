import { Info } from "lucide-react";
import { IS_DEMO } from "@/lib/api";

/**
 * 데모 배포에서 화면 맨 위에 붙는 띠.
 *
 * 닫을 수 없게 두었다. 숫자가 진짜 백엔드에서 나온 값이라 그럴듯해 보이는데,
 * 지금 이 순간의 시세는 아니다. 그 사실은 화면에 계속 남아 있어야 한다.
 */
export default function DemoBanner() {
  if (!IS_DEMO) return null;

  return (
    <div className="border-b border-line bg-warnBg px-4 py-2 text-center text-xs text-warn">
      <p className="mx-auto flex max-w-[1600px] flex-wrap items-center justify-center gap-1.5">
        <Info size={14} className="shrink-0" />
        <span className="font-bold">데모</span>
        <span>
          백엔드 없이 미리 받아둔 응답을 보여줍니다. 값은 고정이며 저장·삭제와 실시간 조회는
          동작하지 않습니다.
        </span>
      </p>
    </div>
  );
}
