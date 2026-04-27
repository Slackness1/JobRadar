import CompanyCard from './CompanyCard';
import type { SiteRow } from './types';

interface CategoryGroupProps {
  label: string;
  rows: SiteRow[];
  selectedCompany: string | null;
  onSelect: (company: string) => void;
}

export default function CategoryGroup({ label, rows, selectedCompany, onSelect }: CategoryGroupProps) {
  return (
    <section className="sites-category-group">
      <header className="sites-category-header">
        <h2 className="sites-category-title">{label}</h2>
        <span className="sites-category-count">({rows.length})</span>
      </header>
      <div className="sites-card-grid">
        {rows.map((row) => (
          <CompanyCard
            key={`${row.source}::${row.company}`}
            row={row}
            selected={row.company === selectedCompany}
            onClick={onSelect}
          />
        ))}
      </div>
    </section>
  );
}
