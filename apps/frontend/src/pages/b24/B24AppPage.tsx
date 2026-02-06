export function B24AppPage() {
  const origin = typeof window !== "undefined" ? window.location.origin : "";
  const handlerUrl = `${origin}/api/v1/bitrix/handler`;
  const installUrl = `${origin}/api/v1/bitrix/install`;

  return (
    <div className="min-h-screen bg-gray-50 p-6">
      <h1 className="text-xl font-bold mb-4">Teachbase AI — Портал</h1>
      <p className="text-gray-600 mb-6">
        Интерфейс внутри Bitrix24 placement. Статус, пользователи, доступ.
      </p>

      <div className="bg-white p-4 rounded-lg shadow mb-4">
        <h2 className="font-semibold mb-2">URL для формы «Локальное приложение»</h2>
        <p className="text-sm text-gray-600 mb-2">
          Путь вашего обработчика:
        </p>
        <code className="block bg-gray-100 p-2 rounded text-sm break-all">{handlerUrl}</code>
        <p className="text-sm text-gray-600 mt-3 mb-2">
          Путь для первоначальной установки:
        </p>
        <code className="block bg-gray-100 p-2 rounded text-sm break-all">{installUrl}</code>
      </div>

      <div className="bg-white p-4 rounded-lg shadow mb-4">
        <h2 className="font-semibold mb-2">Права (scope)</h2>
        <p className="text-sm text-gray-600">imbot, im, placement, user</p>
        <p className="text-xs text-gray-500 mt-1">user — для выбора сотрудников при установке</p>
      </div>
    </div>
  );
}
