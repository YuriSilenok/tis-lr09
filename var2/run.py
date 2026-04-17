from flask import Flask, render_template_string, request, jsonify

app = Flask(__name__)

# Весовые коэффициенты условий
WEIGHTS = {
    'plan_sales': 0.40,  # План продаж (критическое)
    'no_absences': 0.30,  # Отсутствие прогулов (критическое)
    'training': 0.20,  # Прохождение обучения
    'reports': 0.10  # Соблюдение сроков отчетов
}

CRITICAL_CONDITIONS = ['plan_sales', 'no_absences']

HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=yes">
    <title>Корпоративный бонусный калькулятор</title>
    <style>
        * {
            box-sizing: border-box;
            font-family: system-ui, -apple-system, 'Segoe UI', Roboto, 'Helvetica Neue', sans-serif;
        }
        body {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            margin: 0;
            padding: 20px;
            display: flex;
            justify-content: center;
            align-items: center;
        }
        .container {
            max-width: 650px;
            width: 100%;
            background: white;
            border-radius: 32px;
            box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.25);
            overflow: hidden;
            padding: 24px 28px 32px 28px;
            transition: all 0.2s;
        }
        h1 {
            font-size: 1.8rem;
            font-weight: 700;
            color: #1e293b;
            margin: 0 0 8px 0;
            display: flex;
            align-items: center;
            gap: 12px;
            flex-wrap: wrap;
        }
        .subtitle {
            color: #475569;
            border-left: 4px solid #8b5cf6;
            padding-left: 16px;
            margin: 8px 0 24px 0;
            font-size: 0.95rem;
        }
        .card {
            background: #f8fafc;
            border-radius: 24px;
            padding: 20px;
            margin-bottom: 24px;
        }
        .input-group {
            margin-bottom: 20px;
        }
        label {
            display: flex;
            align-items: center;
            gap: 12px;
            font-weight: 600;
            color: #0f172a;
            cursor: pointer;
            padding: 10px 12px;
            background: white;
            border-radius: 16px;
            transition: all 0.2s;
            border: 1px solid #e2e8f0;
            margin-bottom: 8px;
        }
        label:hover {
            background: #f1f5f9;
            border-color: #cbd5e1;
        }
        .condition-checkbox {
            width: 20px;
            height: 20px;
            cursor: pointer;
            accent-color: #8b5cf6;
        }
        .condition-text {
            flex: 1;
            font-size: 1rem;
        }
        .weight-badge {
            font-size: 0.75rem;
            background: #e2e8f0;
            padding: 4px 8px;
            border-radius: 20px;
            font-weight: 500;
            color: #334155;
        }
        .critical-icon {
            font-size: 1.1rem;
        }
        .bonus-input {
            margin-top: 12px;
        }
        .bonus-input label {
            background: #f1f5f9;
            border: 1px solid #e2e8f0;
            cursor: default;
        }
        .bonus-input label:hover {
            background: #f1f5f9;
        }
        input[type="number"] {
            width: 100%;
            padding: 12px 16px;
            font-size: 1rem;
            border: 1px solid #cbd5e1;
            border-radius: 20px;
            font-weight: 500;
            transition: 0.2s;
            background: white;
        }
        input[type="number"]:focus {
            outline: none;
            border-color: #8b5cf6;
            box-shadow: 0 0 0 3px rgba(139, 92, 246, 0.2);
        }
        .result-area {
            background: linear-gradient(105deg, #1e293b 0%, #0f172a 100%);
            border-radius: 24px;
            padding: 20px;
            color: white;
            margin-top: 10px;
        }
        .result-row {
            display: flex;
            justify-content: space-between;
            align-items: baseline;
            padding: 12px 0;
            border-bottom: 1px solid rgba(255,255,255,0.15);
        }
        .result-row:last-child {
            border-bottom: none;
        }
        .result-label {
            font-size: 0.9rem;
            opacity: 0.8;
        }
        .result-value {
            font-weight: 700;
            font-size: 1.3rem;
        }
        .premium-amount {
            font-size: 2rem;
            font-weight: 800;
            color: #fbbf24;
            letter-spacing: -0.02em;
        }
        .badge {
            background: rgba(255,255,255,0.15);
            padding: 6px 12px;
            border-radius: 40px;
            font-size: 0.75rem;
            font-weight: 500;
        }
        button {
            width: 100%;
            background: #ef4444;
            color: white;
            border: none;
            padding: 14px;
            font-weight: 700;
            font-size: 1rem;
            border-radius: 40px;
            cursor: pointer;
            transition: 0.2s;
            margin-top: 16px;
        }
        button:hover {
            background: #dc2626;
            transform: scale(0.98);
        }
        .message {
            margin-top: 16px;
            padding: 12px;
            background: #fef9c3;
            color: #854d0e;
            border-radius: 20px;
            font-size: 0.85rem;
            text-align: center;
        }
        .flex-between {
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        hr {
            margin: 16px 0;
            border: none;
            border-top: 1px solid #e2e8f0;
        }
        @media (max-width: 500px) {
            .container {
                padding: 16px;
            }
            .premium-amount {
                font-size: 1.6rem;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>
            💰 Бонусный калькулятор
            <span class="badge" style="background:#e2e8f0; color:#1e293b;">KPI v2.0</span>
        </h1>
        <div class="subtitle">Учитывает вес условий и бонус за критические показатели</div>

        <div class="card">
            <div class="bonus-input">
                <label>💰 Базовый бонус (₽)</label>
                <input type="number" id="baseBonus" value="10000" step="1000" min="0" max="1000000">
            </div>
        </div>

        <div class="card">
            <h3 style="margin-top:0; margin-bottom:16px; font-size:1.2rem;">📋 Выполнение KPI</h3>
            <div id="conditionsList">
                {% for key, label in conditions_labels.items() %}
                <label>
                    <input type="checkbox" class="condition-checkbox" data-key="{{ key }}" id="chk_{{ key }}">
                    <span class="condition-text">{{ label.name }}</span>
                    <span class="weight-badge">вес {{ "%.0f"|format(label.weight*100) }}%</span>
                    <span class="critical-icon">{{ "🔴 крит." if label.critical else "🟢" }}</span>
                </label>
                {% endfor %}
            </div>
        </div>

        <button id="resetBtn">⟳ Сбросить все условия</button>

        <div class="result-area" id="resultBlock">
            <div class="flex-between" style="margin-bottom: 12px;">
                <span>📊 РЕЗУЛЬТАТ РАСЧЕТА</span>
                <span id="updateTime" style="font-size:0.7rem;">⚡ авто</span>
            </div>
            <div class="result-row">
                <span class="result-label">✅ Выполнено условий:</span>
                <span class="result-value" id="doneCount">0 из 4</span>
            </div>
            <div class="result-row">
                <span class="result-label">⚖️ Сумма весов:</span>
                <span class="result-value" id="totalWeight">0.00</span>
            </div>
            <div class="result-row">
                <span class="result-label">🎯 Коэффициент критичности (Ккрит):</span>
                <span class="result-value" id="kCrit">—</span>
            </div>
            <div class="result-row" style="border-bottom: none; margin-top: 8px;">
                <span class="result-label">🏆 ИТОГОВАЯ ПРЕМИЯ:</span>
                <span class="premium-amount" id="premiumAmount">0 ₽</span>
            </div>
            <div id="specialMessage" style="margin-top: 16px; text-align: center; font-size:0.85rem;"></div>
        </div>
        <div id="errorMessage" style="color:#b91c1c; margin-top: 12px; text-align:center;"></div>
    </div>

    <script>
        // Веса и критичность из Python (передаются в JS)
        const WEIGHTS = {{ weights|tojson }};
        const CRITICAL_KEYS = {{ critical_keys|tojson }};

        // Функция расчета
        function calculateBonus() {
            // Получаем базовый бонус
            let baseBonus = parseFloat(document.getElementById('baseBonus').value);
            if (isNaN(baseBonus)) baseBonus = 10000;
            if (baseBonus < 0) baseBonus = 1000;
            if (baseBonus > 1000000) baseBonus = 1000000;
            if (baseBonus === 0) baseBonus = 1000;

            // Собираем состояние чекбоксов
            const checkboxes = document.querySelectorAll('.condition-checkbox');
            let completedWeights = 0;
            let completedCount = 0;
            let criticalCompleted = 0;

            checkboxes.forEach(cb => {
                const key = cb.getAttribute('data-key');
                const isChecked = cb.checked;
                const weight = WEIGHTS[key] || 0;

                if (isChecked) {
                    completedWeights += weight;
                    completedCount++;
                    if (CRITICAL_KEYS.includes(key)) {
                        criticalCompleted++;
                    }
                }
            });

            // Коэффициент критичности
            let kCrit = 0;
            if (criticalCompleted === 2) {
                kCrit = 1.2;
            } else if (criticalCompleted === 1) {
                kCrit = 1.0;
            } else {
                kCrit = 0.7;
            }

            // Сумма весов выполненных условий
            const totalWeight = completedWeights;

            let premium = 0;
            let errorMsg = '';
            let specialMsg = '';

            if (totalWeight === 0) {
                premium = 0;
                errorMsg = '⚠️ Не выполнено ни одного условия — премия не начисляется.';
            } else {
                premium = baseBonus * totalWeight * kCrit;
                premium = Math.floor(premium); // округление вниз

                if (criticalCompleted === 2 && totalWeight === 1.0) {
                    specialMsg = '🏆 Максимальная премия + бонус за критичность! Отлично!';
                } else if (criticalCompleted === 2) {
                    specialMsg = '🔥 Выполнены все критические условия + бонус 20%';
                } else if (criticalCompleted === 1) {
                    specialMsg = '✅ Выполнено одно критическое условие (Ккрит=1.0)';
                } else {
                    specialMsg = '⚠️ Не выполнены критические условия — снижен Ккрит=0.7';
                }
            }

            // Обновляем UI
            document.getElementById('doneCount').innerText = `${completedCount} из 4`;
            document.getElementById('totalWeight').innerText = totalWeight.toFixed(2);
            document.getElementById('kCrit').innerText = kCrit.toFixed(1);
            document.getElementById('premiumAmount').innerHTML = premium.toLocaleString('ru-RU') + ' ₽';
            document.getElementById('specialMessage').innerHTML = specialMsg;
            document.getElementById('errorMessage').innerHTML = errorMsg;
            document.getElementById('updateTime').innerHTML = new Date().toLocaleTimeString();
        }

        // Сброс всех условий
        function resetAll() {
            const checkboxes = document.querySelectorAll('.condition-checkbox');
            checkboxes.forEach(cb => {
                cb.checked = false;
            });
            document.getElementById('baseBonus').value = 10000;
            calculateBonus();
        }

        // Автообновление при любых изменениях
        function bindEvents() {
            const checkboxes = document.querySelectorAll('.condition-checkbox');
            checkboxes.forEach(cb => {
                cb.addEventListener('change', calculateBonus);
            });
            const bonusInput = document.getElementById('baseBonus');
            bonusInput.addEventListener('input', calculateBonus);
            const resetBtn = document.getElementById('resetBtn');
            resetBtn.addEventListener('click', resetAll);
        }

        // Инициализация
        document.addEventListener('DOMContentLoaded', () => {
            bindEvents();
            calculateBonus();
        });
    </script>
</body>
</html>
'''


@app.route('/')
def index():
    # Подготовка данных для шаблона
    conditions_labels = {
        'plan_sales': {'name': '📈 План продаж', 'weight': WEIGHTS['plan_sales'], 'critical': True},
        'no_absences': {'name': '👤 Отсутствие прогулов', 'weight': WEIGHTS['no_absences'], 'critical': True},
        'training': {'name': '📚 Прохождение обучения', 'weight': WEIGHTS['training'], 'critical': False},
        'reports': {'name': '📅 Соблюдение сроков отчетов', 'weight': WEIGHTS['reports'], 'critical': False}
    }
    return render_template_string(
        HTML_TEMPLATE,
        conditions_labels=conditions_labels,
        weights=WEIGHTS,
        critical_keys=CRITICAL_CONDITIONS
    )


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)