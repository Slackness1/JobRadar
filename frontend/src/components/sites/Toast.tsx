interface ToastProps {
  text: string;
  kind: 'success' | 'failed';
}

export default function Toast({ text, kind }: ToastProps) {
  return <div className={`sites-toast ${kind}`}>{text}</div>;
}
