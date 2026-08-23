import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { ChestArtwork } from "@/components/artwork";
import { RewardReveal } from "@/components/chest/RewardReveal";
import { ScreenHeader } from "@/components/layout/ScreenHeader";
import { Button, ErrorState, Skeleton } from "@/components/ui";
import { useChest, useClaimFreeChest, useFreeChestStatus, useOpenChest } from "@/hooks/useChests";
import { formatNumber } from "@/utils/format";

const isFreeChest = (slug: string) => slug === "free-chest";

// A floor on how long the "opening" (shaking chest) stage stays up before
// the reveal can show, even if the response comes back instantly — without
// this a fast network makes the whole animation invisible. If the request
// is slower than this, the shake just keeps going until the real response
// arrives (this is a minimum, not a fixed delay).
const MIN_SUSPENSE_MS = 1500;

export function ChestOpeningPage() {
  const { chestId } = useParams<{ chestId: string }>();
  const id = Number(chestId);
  const navigate = useNavigate();

  const chest = useChest(id);
  const isFree = chest.data ? isFreeChest(chest.data.slug) : false;

  const freeStatus = useFreeChestStatus();
  const openChest = useOpenChest();
  const claimFree = useClaimFreeChest();

  const mutation = isFree ? claimFree : openChest;
  const result = mutation.data;

  const [opening, setOpening] = useState(false);
  const [suspenseElapsed, setSuspenseElapsed] = useState(false);

  useEffect(() => {
    if (!opening) return;
    const timer = setTimeout(() => setSuspenseElapsed(true), MIN_SUSPENSE_MS);
    return () => clearTimeout(timer);
  }, [opening]);

  useEffect(() => {
    if (mutation.isError) {
      setOpening(false);
      setSuspenseElapsed(false);
    }
  }, [mutation.isError]);

  if (chest.isPending) {
    return (
      <div>
        <ScreenHeader title="Сундук" />
        <div className="px-4">
          <Skeleton className="aspect-[3/4]" />
        </div>
      </div>
    );
  }

  if (chest.isError) {
    return (
      <div>
        <ScreenHeader title="Сундук" />
        <div className="p-4">
          <ErrorState error={chest.error} onRetry={() => chest.refetch()} />
        </div>
      </div>
    );
  }

  const c = chest.data;

  if (opening && suspenseElapsed && result) {
    return (
      <div className="pb-6">
        <ScreenHeader title="Награда" />
        <RewardReveal reward={result.reward} />
        <div className="px-4">
          <Button className="w-full" onClick={() => navigate(-1)}>
            Продолжить
          </Button>
        </div>
      </div>
    );
  }

  if (opening) {
    return (
      <div className="pb-6">
        <ScreenHeader title={c.name} />
        <div className="px-4">
          <ChestArtwork chest={c} size="detail" className="w-full animate-chest-shake" />
          <p className="mt-5 text-center font-mono text-[12px] text-ink-dim">Открываем...</p>
        </div>
      </div>
    );
  }

  function handleOpen() {
    setOpening(true);
    setSuspenseElapsed(false);
    if (isFree) claimFree.mutate();
    else openChest.mutate(id);
  }

  const notAvailable = isFree && freeStatus.data && !freeStatus.data.is_available;

  return (
    <div className="pb-6">
      <ScreenHeader title={c.name} />
      <div className="px-4">
        <ChestArtwork chest={c} size="detail" className="w-full" />

        <div className="mt-4 text-center">
          <p className="font-display text-xl font-semibold text-ink">{c.name}</p>
          <p className="mt-1 font-mono text-[12px] text-ink-dim">
            {isFree ? "Бесплатно · раз в 24ч" : `${formatNumber(c.price)} ⏣`}
          </p>
        </div>

        {mutation.isError && (
          <div className="mt-4">
            <ErrorState error={mutation.error} />
          </div>
        )}

        {notAvailable && freeStatus.data?.next_available_at && (
          <p className="mt-4 text-center font-mono text-[11px] text-ink-dim">
            Следующий бесплатный сундук: {new Date(freeStatus.data.next_available_at).toLocaleString("ru-RU")}
          </p>
        )}

        <Button className="mt-5 w-full" disabled={notAvailable} onClick={handleOpen}>
          Открыть
        </Button>
      </div>
    </div>
  );
}
