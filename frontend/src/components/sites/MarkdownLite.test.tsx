import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import MarkdownLite from './MarkdownLite';

describe('MarkdownLite', () => {
  it('renders **bold** as <strong>', () => {
    const { container } = render(<MarkdownLite text="**可能原因**：selector 变了" />);
    const strong = container.querySelector('strong');
    expect(strong).not.toBeNull();
    expect(strong!.textContent).toBe('可能原因');
  });

  it('renders `code` as <code>', () => {
    const { container } = render(<MarkdownLite text="改成 `.position-card` 即可" />);
    const code = container.querySelector('code');
    expect(code).not.toBeNull();
    expect(code!.textContent).toBe('.position-card');
  });

  it('splits blank-line-separated paragraphs', () => {
    const { container } = render(<MarkdownLite text={'第一段\n\n第二段'} />);
    expect(container.querySelectorAll('.md-lite-p').length).toBe(2);
  });

  it('renders numbered list when all lines start with N.', () => {
    const text = '1. 第一步\n2. 第二步\n3. 第三步';
    const { container } = render(<MarkdownLite text={text} />);
    const ol = container.querySelector('ol.md-lite-list');
    expect(ol).not.toBeNull();
    expect(ol!.querySelectorAll('li').length).toBe(3);
  });

  it('preserves line breaks within a paragraph as <br>', () => {
    const { container } = render(<MarkdownLite text={'第一行\n第二行'} />);
    expect(container.querySelectorAll('br').length).toBe(1);
  });

  it('mixes bold and code inline', () => {
    render(<MarkdownLite text="**改动**：把 `.a` 替换成 `.b`" />);
    expect(screen.getByText('改动')).toBeInTheDocument();
    expect(screen.getByText('.a')).toBeInTheDocument();
    expect(screen.getByText('.b')).toBeInTheDocument();
  });
});
