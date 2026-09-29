import { useState } from 'react';

export default function CandidateThumbnail({ media, name }) {
  const [failed, setFailed] = useState(false);
  return <span className="candidate-thumbnail">{media?.url && !failed
    ? <img src={media.url} width={media.width_px} height={media.height_px} alt={`Изображение модели ${name}`}
      loading="lazy" decoding="async" onError={() => setFailed(true)} />
    : <span role="img" aria-label={`Изображение модели ${name} ${failed ? 'не загрузилось' : 'отсутствует'}`}>Изображение недоступно</span>}</span>;
}
