export function toBeijingTime(isoStr: string | null): string {
  if (!isoStr) return '-';
  try {
    const date = new Date(isoStr);
    if (isNaN(date.getTime())) return isoStr.slice(0, 19);
    return date.toLocaleString('zh-CN', {
      timeZone: 'Asia/Shanghai',
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hour12: false,
    });
  } catch {
    return isoStr.slice(0, 19);
  }
}

export function relativeTime(isoStr: string | null): string {
  if (!isoStr) return '-';
  try {
    const date = new Date(isoStr);
    if (isNaN(date.getTime())) return '-';
    const now = Date.now();
    const diff = now - date.getTime();
    const seconds = Math.floor(diff / 1000);
    if (seconds < 30) return '刚刚';
    if (seconds < 60) return `${seconds}秒前`;
    const minutes = Math.floor(seconds / 60);
    if (minutes < 60) return `${minutes}分钟前`;
    const hours = Math.floor(minutes / 60);
    if (hours < 24) return `${hours}小时前`;
    const days = Math.floor(hours / 24);
    return `${days}天前`;
  } catch {
    return '-';
  }
}
