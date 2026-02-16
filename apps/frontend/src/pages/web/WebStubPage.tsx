export function WebStubPage({ title }: { title: string }) {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-slate-900">{title}</h1>
        <p className="text-sm text-slate-500 mt-1">Новый интерфейс в разработке. Пока используйте старый дизайн.</p>
      </div>
      <div className="rounded-2xl border border-dashed border-slate-200 bg-white p-8 text-sm text-slate-500">
        Раздел будет перенесён в React. Здесь появятся таблицы, фильтры и настройки.
      </div>
    </div>
  );
}
