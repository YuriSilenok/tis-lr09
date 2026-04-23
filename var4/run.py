from flask import Flask, render_template_string, request, jsonify, redirect, url_for, Response
from datetime import datetime
import json
import os
import csv
from io import StringIO

app = Flask(__name__)
app.secret_key = 'electricity-calculator-secret-key'

# ==================== КОНФИГУРАЦИЯ ====================
CONFIG = {
    'tariff_peak': 6.50,          # руб/кВт⋅ч
    'tariff_half_peak': 5.00,     # руб/кВт⋅ч
    'tariff_night': 2.30,         # руб/кВт⋅ч
    'social_norm': 150,           # кВт⋅ч в месяц
    'excess_coefficient': 1.5,    # коэффициент при превышении нормы
    'discount_percent': 30,       # процент скидки при льготе
    'round_digits': 2             # округление до копеек
}

# ==================== ДАННЫЕ ====================
DATA_FILE = 'electricity_data.json'


def load_data():
    """Загружает данные из JSON-файла"""
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {
        'records': [],
        'settings': CONFIG
    }


def save_data(data):
    """Сохраняет данные в JSON-файл"""
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ==================== БИЗНЕС-ЛОГИКА ====================
def calculate_cost(record, settings):
    """
    Рассчитывает стоимость электроэнергии по правилам варианта 4.
    Возвращает словарь с итоговой стоимостью, деталями и комментарием.
    """
    peak = record.get('peak', 0)
    half_peak = record.get('half_peak', 0)
    night = record.get('night', 0)
    has_benefit = record.get('has_benefit', False)

    # Суммарное потребление
    total_consumption = peak + half_peak + night

    # Определение коэффициента социальной нормы
    if total_consumption > settings['social_norm']:
        coefficient = settings['excess_coefficient']
        norm_status = f"Превышение нормы {settings['social_norm']} кВт⋅ч (коэф. {coefficient})"
    else:
        coefficient = 1.0
        norm_status = f"В пределах нормы {settings['social_norm']} кВт⋅ч"

    # Расчёт стоимости по зонам
    cost_peak = peak * settings['tariff_peak']
    cost_half_peak = half_peak * settings['tariff_half_peak']
    cost_night = night * settings['tariff_night']
    subtotal = cost_peak + cost_half_peak + cost_night

    # Применение коэффициента
    total_before_discount = subtotal * coefficient

    # Применение льготы
    if has_benefit:
        final_cost = total_before_discount * (1 - settings['discount_percent'] / 100)
        benefit_status = f"Применена льгота {settings['discount_percent']}%"
    else:
        final_cost = total_before_discount
        benefit_status = "Льгота отсутствует"

    final_cost = round(final_cost, settings['round_digits'])

    details = {
        'total_consumption': total_consumption,
        'norm_status': norm_status,
        'coefficient': coefficient,
        'cost_peak': round(cost_peak, 2),
        'cost_half_peak': round(cost_half_peak, 2),
        'cost_night': round(cost_night, 2),
        'subtotal': round(subtotal, 2),
        'total_before_discount': round(total_before_discount, 2),
        'benefit_status': benefit_status
    }

    return {
        'final_cost': final_cost,
        'details': details,
        'comment': f"{norm_status}. {benefit_status}."
    }


# ==================== HTML ШАБЛОН ====================
INDEX_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>Калькулятор стоимости электроэнергии</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: #f5f5f5; padding: 20px; }
        .container { max-width: 1400px; margin: 0 auto; }
        h1 { color: #333; margin-bottom: 20px; }
        .controls { background: white; padding: 20px; border-radius: 8px; margin-bottom: 20px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        button { background: #007bff; color: white; border: none; padding: 10px 20px; border-radius: 5px; cursor: pointer; margin-right: 10px; }
        button:hover { background: #0056b3; }
        .btn-danger { background: #dc3545; }
        .btn-danger:hover { background: #c82333; }
        .btn-success { background: #28a745; }
        .btn-success:hover { background: #218838; }
        table { width: 100%; background: white; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        th, td { padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }
        th { background: #007bff; color: white; }
        tr:hover { background: #f5f5f5; }
        .modal { display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.5); z-index: 1000; }
        .modal-content { background: white; margin: 5% auto; padding: 20px; width: 90%; max-width: 600px; border-radius: 8px; }
        .form-group { margin-bottom: 15px; }
        label { display: block; margin-bottom: 5px; font-weight: bold; }
        input, select { width: 100%; padding: 8px; border: 1px solid #ddd; border-radius: 4px; }
        .close { float: right; cursor: pointer; font-size: 24px; }
        .settings-panel { background: white; padding: 20px; border-radius: 8px; margin-bottom: 20px; }
        .weight-input { width: 80px; display: inline-block; margin: 0 10px; }
        .cost-highlight { font-weight: bold; }
        .details-btn { background: #17a2b8; padding: 5px 10px; font-size: 12px; }
    </style>
</head>
<body>
    <div class="container">
        <h1>⚡ Калькулятор стоимости электроэнергии (трёхзонный тариф)</h1>

        <div class="controls">
            <button onclick="showAddRecordModal()">➕ Добавить расчёт</button>
            <button onclick="calculateAll()">🔄 Пересчитать все</button>
            <button onclick="showSettings()">⚙️ Настройки тарифов</button>
            <button onclick="exportResults()">📊 Экспорт в CSV</button>
        </div>

        <div id="recordsTable">
            {{ records_html|safe }}
        </div>
    </div>

    <!-- Модальное окно добавления записи -->
    <div id="addRecordModal" class="modal">
        <div class="modal-content">
            <span class="close" onclick="closeModal()">&times;</span>
            <h2>Новый расчёт</h2>
            <form id="recordForm">
                <div class="form-group">
                    <label>Название / адрес:</label>
                    <input type="text" name="name" placeholder="Например: кв. 42" required>
                </div>
                <div class="form-group">
                    <label>Потребление в пиковой зоне (кВт⋅ч):</label>
                    <input type="number" name="peak" step="any" min="0" required>
                </div>
                <div class="form-group">
                    <label>Потребление в полупиковой зоне (кВт⋅ч):</label>
                    <input type="number" name="half_peak" step="any" min="0" required>
                </div>
                <div class="form-group">
                    <label>Потребление в ночной зоне (кВт⋅ч):</label>
                    <input type="number" name="night" step="any" min="0" required>
                </div>
                <div class="form-group">
                    <label>Наличие льготы (скидка 30%):</label>
                    <select name="has_benefit">
                        <option value="false">Нет</option>
                        <option value="true">Да</option>
                    </select>
                </div>
                <button type="submit">Рассчитать и сохранить</button>
            </form>
        </div>
    </div>

    <script>
        function closeModal() {
            document.getElementById('addRecordModal').style.display = 'none';
        }

        function showAddRecordModal() {
            document.getElementById('addRecordModal').style.display = 'block';
        }

        document.getElementById('recordForm').onsubmit = async (e) => {
            e.preventDefault();
            const formData = new FormData(e.target);
            const data = {};
            for (let [key, value] of formData.entries()) {
                if (value === 'true') data[key] = true;
                else if (value === 'false') data[key] = false;
                else if (!isNaN(value) && value !== '') data[key] = parseFloat(value);
                else data[key] = value;
            }

            const response = await fetch('/api/record', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(data)
            });

            if (response.ok) {
                location.reload();
            } else {
                alert('Ошибка при добавлении записи');
            }
        };

        async function calculateAll() {
            const response = await fetch('/api/calculate_all', {method: 'POST'});
            if (response.ok) {
                location.reload();
            }
        }

        async function showSettings() {
            const response = await fetch('/api/settings');
            const settings = await response.json();

            let html = '<div class="settings-panel"><h2>Настройки тарифов и лимитов</h2><form id="settingsForm">';
            html += '<h3>Тарифы (руб/кВт⋅ч):</h3>';
            html += `<label>Пиковая зона: <input type="number" step="0.01" name="tariff_peak" value="${settings.tariff_peak}"></label><br>`;
            html += `<label>Полупиковая зона: <input type="number" step="0.01" name="tariff_half_peak" value="${settings.tariff_half_peak}"></label><br>`;
            html += `<label>Ночная зона: <input type="number" step="0.01" name="tariff_night" value="${settings.tariff_night}"></label><br>`;
            html += '<h3>Социальная норма:</h3>';
            html += `<label>Лимит (кВт⋅ч): <input type="number" name="social_norm" value="${settings.social_norm}"></label><br>`;
            html += `<label>Коэффициент превышения: <input type="number" step="0.1" name="excess_coefficient" value="${settings.excess_coefficient}"></label><br>`;
            html += '<h3>Льгота:</h3>';
            html += `<label>Скидка (%): <input type="number" step="1" name="discount_percent" value="${settings.discount_percent}"></label><br>`;
            html += '<button type="submit">Сохранить</button></form></div>';

            const modal = document.createElement('div');
            modal.className = 'modal';
            modal.style.display = 'block';
            modal.innerHTML = `<div class="modal-content"><span class="close" onclick="this.parentElement.parentElement.remove()">&times;</span>${html}</div>`;
            document.body.appendChild(modal);

            document.getElementById('settingsForm').onsubmit = async (e) => {
                e.preventDefault();
                const formData = new FormData(e.target);
                const data = {};
                for (let [key, value] of formData.entries()) {
                    data[key] = parseFloat(value);
                }

                await fetch('/api/settings', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify(data)
                });
                location.reload();
            };
        }

        async function exportResults() {
            window.location.href = '/export/csv';
        }

        async function deleteRecord(id) {
            if (confirm('Удалить запись?')) {
                await fetch(`/api/record/${id}`, {method: 'DELETE'});
                location.reload();
            }
        }

        async function recalculateRecord(id) {
            await fetch(`/api/calculate/${id}`, {method: 'POST'});
            location.reload();
        }

        function showDetails(detailsJson) {
            const details = JSON.parse(detailsJson);
            let html = '<h3>Детали расчёта</h3>';
            html += `<p>Общее потребление: ${details.total_consumption} кВт⋅ч</p>`;
            html += `<p>Статус нормы: ${details.norm_status}</p>`;
            html += `<p>Коэффициент: ${details.coefficient}</p>`;
            html += `<p>Стоимость пик: ${details.cost_peak} руб.</p>`;
            html += `<p>Стоимость полупик: ${details.cost_half_peak} руб.</p>`;
            html += `<p>Стоимость ночь: ${details.cost_night} руб.</p>`;
            html += `<p>Подытог (без коэф.): ${details.subtotal} руб.</p>`;
            html += `<p>Стоимость до льготы: ${details.total_before_discount} руб.</p>`;
            html += `<p>${details.benefit_status}</p>`;
            alert(html.replace(/<[^>]*>/g, '')); // Упрощённый вывод
        }
    </script>
</body>
</html>
'''


# ==================== FLASK МАРШРУТЫ ====================
@app.route('/')
def index():
    data = load_data()

    records_html = '''
    <table>
        <thead>
            <tr>
                <th>ID</th><th>Название</th><th>Пик (кВт⋅ч)</th><th>Полупик (кВт⋅ч)</th><th>Ночь (кВт⋅ч)</th>
                <th>Всего (кВт⋅ч)</th><th>Льгота</th><th>Итоговая стоимость (руб)</th><th>Действия</th>
            </tr>
        </thead>
        <tbody>
    '''

    for rec in data['records']:
        total_cons = rec.get('peak', 0) + rec.get('half_peak', 0) + rec.get('night', 0)
        benefit_text = "Да" if rec.get('has_benefit', False) else "Нет"
        records_html += f'''
            <tr>
                <td>{rec.get('id')}</td>
                <td>{rec.get('name', 'Без названия')}</td>
                <td>{rec.get('peak', 0)}</td>
                <td>{rec.get('half_peak', 0)}</td>
                <td>{rec.get('night', 0)}</td>
                <td>{total_cons}</td>
                <td>{benefit_text}</td>
                <td class="cost-highlight">{rec.get('final_cost', 0)}</td>
                <td>
                    <button onclick="recalculateRecord({rec.get('id')})" title="Пересчитать">🔄</button>
                    <button onclick="deleteRecord({rec.get('id')})" style="background:#dc3545" title="Удалить">🗑️</button>
                    <button onclick="showDetails('{json.dumps(rec.get('details', {}), ensure_ascii=False).replace("'", "\\'")}')" class="details-btn" title="Детали">ℹ️</button>
                </td>
            </tr>
        '''

    records_html += '</tbody></table>'
    return render_template_string(INDEX_TEMPLATE, records_html=records_html)


@app.route('/api/record', methods=['POST'])
def add_record():
    data = load_data()
    record = request.json

    # Генерируем ID
    record['id'] = max([r.get('id', 0) for r in data['records']] + [0]) + 1
    record['created_at'] = datetime.now().isoformat()

    # Сразу рассчитываем стоимость
    result = calculate_cost(record, data['settings'])
    record['final_cost'] = result['final_cost']
    record['details'] = result['details']
    record['comment'] = result['comment']

    data['records'].append(record)
    save_data(data)
    return jsonify({'success': True, 'id': record['id']})


@app.route('/api/record/<int:record_id>', methods=['DELETE'])
def delete_record(record_id):
    data = load_data()
    data['records'] = [r for r in data['records'] if r.get('id') != record_id]
    save_data(data)
    return jsonify({'success': True})


@app.route('/api/calculate/<int:record_id>', methods=['POST'])
def calculate_record(record_id):
    data = load_data()
    for rec in data['records']:
        if rec.get('id') == record_id:
            result = calculate_cost(rec, data['settings'])
            rec['final_cost'] = result['final_cost']
            rec['details'] = result['details']
            rec['comment'] = result['comment']
            break

    save_data(data)
    return jsonify({'success': True})


@app.route('/api/calculate_all', methods=['POST'])
def calculate_all():
    data = load_data()
    for rec in data['records']:
        result = calculate_cost(rec, data['settings'])
        rec['final_cost'] = result['final_cost']
        rec['details'] = result['details']
        rec['comment'] = result['comment']

    save_data(data)
    return jsonify({'success': True})


@app.route('/api/settings', methods=['GET', 'POST'])
def settings():
    data = load_data()

    if request.method == 'GET':
        return jsonify(data['settings'])
    else:
        new_settings = request.json
        for key, value in new_settings.items():
            if key in data['settings']:
                data['settings'][key] = value
        save_data(data)
        return jsonify({'success': True})


@app.route('/export/csv')
def export_csv():
    data = load_data()
    output = StringIO()
    writer = csv.writer(output)

    writer.writerow([
        'ID', 'Название', 'Пик (кВт⋅ч)', 'Полупик (кВт⋅ч)', 'Ночь (кВт⋅ч)',
        'Всего (кВт⋅ч)', 'Льгота', 'Итоговая стоимость (руб)', 'Комментарий', 'Дата создания'
    ])

    for rec in data['records']:
        total = rec.get('peak', 0) + rec.get('half_peak', 0) + rec.get('night', 0)
        writer.writerow([
            rec.get('id'),
            rec.get('name', ''),
            rec.get('peak', 0),
            rec.get('half_peak', 0),
            rec.get('night', 0),
            total,
            'Да' if rec.get('has_benefit', False) else 'Нет',
            rec.get('final_cost', 0),
            rec.get('comment', ''),
            rec.get('created_at', '')
        ])

    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={"Content-Disposition": "attachment;filename=electricity_calculations.csv"}
    )


if __name__ == '__main__':
    # Создаём тестовые данные при первом запуске
    if not os.path.exists(DATA_FILE):
        test_data = {
            'records': [
                {
                    'id': 1,
                    'name': 'Квартира 15',
                    'peak': 70,
                    'half_peak': 60,
                    'night': 40,
                    'has_benefit': False,
                    'created_at': datetime.now().isoformat()
                },
                {
                    'id': 2,
                    'name': 'Квартира 22 (льготная)',
                    'peak': 50,
                    'half_peak': 30,
                    'night': 20,
                    'has_benefit': True,
                    'created_at': datetime.now().isoformat()
                },
                {
                    'id': 3,
                    'name': 'Офис 3',
                    'peak': 120,
                    'half_peak': 80,
                    'night': 10,
                    'has_benefit': False,
                    'created_at': datetime.now().isoformat()
                }
            ],
            'settings': CONFIG
        }
        # Рассчитаем тестовые записи
        for rec in test_data['records']:
            result = calculate_cost(rec, test_data['settings'])
            rec['final_cost'] = result['final_cost']
            rec['details'] = result['details']
            rec['comment'] = result['comment']
        save_data(test_data)

    app.run(debug=True, port=5001)  # Порт изменён, чтобы не конфликтовать с вариантом 1
