from flask import Flask, render_template_string, request, jsonify, session, redirect, url_for
from datetime import datetime
import json
import os

app = Flask(__name__)
app.secret_key = 'your-secret-key-here-change-in-production'

# ==================== КОНФИГУРАЦИЯ ====================
CONFIG = {
    'base_scholarship': 2000.0,          # Базовая стипендия (руб.)
    'weights': {
        'study': 0.3,    # Вес учебных достижений
        'science': 0.5,  # Вес научных достижений
        'sport': 0.2     # Вес спортивных/культурных достижений
    },
    # Пороги для повышающих коэффициентов (баллы ИПД)
    'threshold_2x': 80,
    'threshold_1_5x': 60,
    'threshold_1_2x': 40
}

# ==================== ДАННЫЕ ====================
STUDENTS_FILE = 'scholarship_data.json'

def load_students():
    if os.path.exists(STUDENTS_FILE):
        with open(STUDENTS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {
        'students': [],
        'settings': CONFIG
    }

def save_students(data):
    with open(STUDENTS_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# ==================== БИЗНЕС-ЛОГИКА ====================
def calculate_scholarship(student, weights, settings):
    """Расчёт стипендии и интегрального показателя достижений (ИПД)"""
    blocks = []
    
    # 1. Академическая задолженность
    if student.get('academic_debt', False):
        blocks.append("Академическая задолженность за прошлый семестр")
    
    # 2. Нарушения дисциплины
    if student.get('discipline_violation', False):
        blocks.append("Наличие дисциплинарных взысканий")
    
    # 3. Средний балл
    avg_grade = student.get('avg_grade', 0.0)
    if avg_grade < 4.0:
        blocks.append(f"Средний балл ниже 4.0 (текущий: {avg_grade})")
    
    # Если есть блокирующие факторы - стипендия 0
    if blocks:
        return {
            'ipd': 0.0,
            'scholarship': 0.0,
            'multiplier': 0.0,
            'blocks': blocks,
            'status': 'Не назначена (блокирующий фактор)'
        }
    
    # Расчёт ИПД
    study_score = student.get('study_achievements', 0)
    science_score = student.get('science_achievements', 0)
    sport_score = student.get('sport_achievements', 0)
    
    ipd = (weights['study'] * study_score + 
           weights['science'] * science_score + 
           weights['sport'] * sport_score)
    
    # Определение множителя
    if ipd >= settings['threshold_2x']:
        multiplier = 2.0
        status = 'Повышенная x2.0'
    elif ipd >= settings['threshold_1_5x']:
        multiplier = 1.5
        status = 'Повышенная x1.5'
    elif ipd >= settings['threshold_1_2x']:
        multiplier = 1.2
        status = 'Повышенная x1.2'
    else:
        multiplier = 1.0
        status = 'Базовая'
    
    scholarship = settings['base_scholarship'] * multiplier
    
    return {
        'ipd': round(ipd, 2),
        'scholarship': round(scholarship, 2),
        'multiplier': multiplier,
        'blocks': [],
        'status': status
    }

# ==================== HTML ШАБЛОНЫ ====================
INDEX_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>Система расчёта стипендии (ПГАС)</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: #f5f5f5; padding: 20px; }
        .container { max-width: 1600px; margin: 0 auto; }
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
        .status-pass { color: #28a745; font-weight: bold; }
        .status-fail { color: #dc3545; font-weight: bold; }
        .modal { display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.5); z-index: 1000; }
        .modal-content { background: white; margin: 5% auto; padding: 20px; width: 90%; max-width: 600px; border-radius: 8px; }
        .form-group { margin-bottom: 15px; }
        label { display: block; margin-bottom: 5px; font-weight: bold; }
        input, select { width: 100%; padding: 8px; border: 1px solid #ddd; border-radius: 4px; }
        .close { float: right; cursor: pointer; font-size: 24px; }
        .settings-panel { background: white; padding: 20px; border-radius: 8px; margin-bottom: 20px; }
        .weight-input { width: 80px; display: inline-block; margin: 0 10px; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🎓 Система расчёта стипендии (ПГАС)</h1>

        <div class="controls">
            <button onclick="showAddStudentModal()">➕ Добавить студента</button>
            <button onclick="calculateAll()">🔄 Рассчитать всех</button>
            <button onclick="showSettings()">⚙️ Настройки</button>
            <button onclick="exportResults()">📊 Экспорт в CSV</button>
        </div>

        <div id="studentsTable">
            {{ students_html|safe }}
        </div>
    </div>

    <!-- Модальное окно добавления студента -->
    <div id="addStudentModal" class="modal">
        <div class="modal-content">
            <span class="close" onclick="closeModal()">&times;</span>
            <h2>Добавить студента</h2>
            <form id="studentForm">
                <div class="form-group">
                    <label>ФИО:</label>
                    <input type="text" name="name" required>
                </div>
                <div class="form-group">
                    <label>Группа:</label>
                    <input type="text" name="group" required>
                </div>
                <div class="form-group">
                    <label>Средний балл (0-5):</label>
                    <input type="number" name="avg_grade" step="0.01" min="0" max="5" required>
                </div>
                <div class="form-group">
                    <label>Академическая задолженность:</label>
                    <select name="academic_debt">
                        <option value="false">Нет</option>
                        <option value="true">Да</option>
                    </select>
                </div>
                <div class="form-group">
                    <label>Нарушения дисциплины:</label>
                    <select name="discipline_violation">
                        <option value="false">Нет</option>
                        <option value="true">Да</option>
                    </select>
                </div>
                <div class="form-group">
                    <label>Учебные достижения (0-100):</label>
                    <input type="number" name="study_achievements" min="0" max="100" required>
                </div>
                <div class="form-group">
                    <label>Научные достижения (0-100):</label>
                    <input type="number" name="science_achievements" min="0" max="100" required>
                </div>
                <div class="form-group">
                    <label>Спортивные/культурные достижения (0-100):</label>
                    <input type="number" name="sport_achievements" min="0" max="100" required>
                </div>
                <button type="submit">Сохранить</button>
            </form>
        </div>
    </div>

    <script>
        function closeModal() {
            document.getElementById('addStudentModal').style.display = 'none';
        }

        function showAddStudentModal() {
            document.getElementById('addStudentModal').style.display = 'block';
        }

        document.getElementById('studentForm').onsubmit = async (e) => {
            e.preventDefault();
            const formData = new FormData(e.target);
            const data = {};
            for (let [key, value] of formData.entries()) {
                if (value === 'true') data[key] = true;
                else if (value === 'false') data[key] = false;
                else if (!isNaN(value) && value !== '') data[key] = parseFloat(value);
                else data[key] = value;
            }

            const response = await fetch('/api/student', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(data)
            });

            if (response.ok) {
                location.reload();
            } else {
                alert('Ошибка при добавлении студента');
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

            let html = '<div class="settings-panel"><h2>Настройки расчёта</h2><form id="settingsForm">';
            html += `<label>Базовая стипендия (руб.): <input type="number" step="100" name="base_scholarship" value="${settings.base_scholarship}"></label><br>`;
            html += '<h3>Весовые коэффициенты достижений (сумма = 1):</h3>';
            html += `<label>Учебные: <input type="number" step="0.05" name="study" value="${settings.weights.study}" class="weight-input"></label><br>`;
            html += `<label>Научные: <input type="number" step="0.05" name="science" value="${settings.weights.science}" class="weight-input"></label><br>`;
            html += `<label>Спортивные/культурные: <input type="number" step="0.05" name="sport" value="${settings.weights.sport}" class="weight-input"></label><br>`;
            html += '<h3>Пороги ИПД для повышения:</h3>';
            html += `<label>Порог x2.0 (баллы): <input type="number" step="1" name="threshold_2x" value="${settings.threshold_2x}"></label><br>`;
            html += `<label>Порог x1.5 (баллы): <input type="number" step="1" name="threshold_1_5x" value="${settings.threshold_1_5x}"></label><br>`;
            html += `<label>Порог x1.2 (баллы): <input type="number" step="1" name="threshold_1_2x" value="${settings.threshold_1_2x}"></label><br>`;
            html += '<button type="submit">Сохранить</button></form></div>';

            const modal = document.createElement('div');
            modal.className = 'modal';
            modal.style.display = 'block';
            modal.innerHTML = `<div class="modal-content"><span class="close" onclick="this.parentElement.parentElement.remove()">&times;</span>${html}</div>`;
            document.body.appendChild(modal);

            document.getElementById('settingsForm').onsubmit = async (e) => {
                e.preventDefault();
                const formData = new FormData(e.target);
                const data = {
                    base_scholarship: parseFloat(formData.get('base_scholarship')),
                    weights: {
                        study: parseFloat(formData.get('study')),
                        science: parseFloat(formData.get('science')),
                        sport: parseFloat(formData.get('sport'))
                    },
                    threshold_2x: parseFloat(formData.get('threshold_2x')),
                    threshold_1_5x: parseFloat(formData.get('threshold_1_5x')),
                    threshold_1_2x: parseFloat(formData.get('threshold_1_2x'))
                };

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

        async function deleteStudent(id) {
            if (confirm('Удалить студента?')) {
                await fetch(`/api/student/${id}`, {method: 'DELETE'});
                location.reload();
            }
        }

        async function recalculateStudent(id) {
            await fetch(`/api/calculate/${id}`, {method: 'POST'});
            location.reload();
        }
    </script>
</body>
</html>
'''

# ==================== FLASK МАРШРУТЫ ====================
@app.route('/')
def index():
    data = load_students()

    students_html = '''
    <table>
        <thead>
            <tr>
                <th>ФИО</th><th>Группа</th><th>Ср. балл</th><th>Акад. долг</th><th>Дисц. нар.</th>
                <th>Учеб. дост.</th><th>Науч. дост.</th><th>Спорт. дост.</th>
                <th>ИПД</th><th>Стипендия (руб.)</th><th>Статус</th><th>Действия</th>
            </tr>
        </thead>
        <tbody>
    '''

    for student in data['students']:
        status_class = 'status-pass' if student.get('scholarship', 0) > 0 else 'status-fail'
        students_html += f'''
            <tr>
                <td>{student['name']}</td>
                <td>{student['group']}</td>
                <td>{student.get('avg_grade', 0)}</td>
                <td>{"Да" if student.get('academic_debt', False) else "Нет"}</td>
                <td>{"Да" if student.get('discipline_violation', False) else "Нет"}</td>
                <td>{student.get('study_achievements', 0)}</td>
                <td>{student.get('science_achievements', 0)}</td>
                <td>{student.get('sport_achievements', 0)}</td>
                <td>{student.get('ipd', 0)}</td>
                <td>{student.get('scholarship', 0)}</td>
                <td class="{status_class}">{student.get('status', 'Не рассчитан')}</td>
                <td>
                    <button onclick="recalculateStudent({student['id']})">🔄</button>
                    <button onclick="deleteStudent({student['id']})" style="background:#dc3545">🗑️</button>
                </td>
            </tr>
        '''

    students_html += '</tbody></table>'
    return render_template_string(INDEX_TEMPLATE, students_html=students_html)

@app.route('/api/student', methods=['POST'])
def add_student():
    data = load_students()
    student = request.json
    student['id'] = max([s.get('id', 0) for s in data['students']] + [0]) + 1
    student['ipd'] = 0
    student['scholarship'] = 0
    student['status'] = 'Не рассчитан'
    data['students'].append(student)
    save_students(data)
    return jsonify({'success': True})

@app.route('/api/student/<int:student_id>', methods=['DELETE'])
def delete_student(student_id):
    data = load_students()
    data['students'] = [s for s in data['students'] if s.get('id') != student_id]
    save_students(data)
    return jsonify({'success': True})

@app.route('/api/calculate/<int:student_id>', methods=['POST'])
def calculate_student(student_id):
    data = load_students()
    for student in data['students']:
        if student.get('id') == student_id:
            result = calculate_scholarship(student, data['settings']['weights'], data['settings'])
            student['ipd'] = result['ipd']
            student['scholarship'] = result['scholarship']
            student['status'] = result['status']
            student['blocks'] = result['blocks']
            break
    save_students(data)
    return jsonify({'success': True})

@app.route('/api/calculate_all', methods=['POST'])
def calculate_all():
    data = load_students()
    for student in data['students']:
        result = calculate_scholarship(student, data['settings']['weights'], data['settings'])
        student['ipd'] = result['ipd']
        student['scholarship'] = result['scholarship']
        student['status'] = result['status']
        student['blocks'] = result['blocks']
    save_students(data)
    return jsonify({'success': True})

@app.route('/api/settings', methods=['GET', 'POST'])
def settings():
    data = load_students()
    if request.method == 'GET':
        return jsonify(data['settings'])
    else:
        new_settings = request.json
        # Обновление настроек с проверкой структуры
        if 'base_scholarship' in new_settings:
            data['settings']['base_scholarship'] = float(new_settings['base_scholarship'])
        if 'weights' in new_settings:
            for key in new_settings['weights']:
                data['settings']['weights'][key] = float(new_settings['weights'][key])
        for key in ['threshold_2x', 'threshold_1_5x', 'threshold_1_2x']:
            if key in new_settings:
                data['settings'][key] = float(new_settings[key])
        save_students(data)
        return jsonify({'success': True})

@app.route('/export/csv')
def export_csv():
    import csv
    from io import StringIO
    data = load_students()
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(['ФИО', 'Группа', 'Средний балл', 'Акад. долг', 'Дисц. нар.',
                     'Учеб. дост.', 'Науч. дост.', 'Спорт. дост.', 'ИПД', 'Стипендия', 'Статус', 'Блокирующие факторы'])
    for student in data['students']:
        writer.writerow([
            student['name'], student['group'], student.get('avg_grade', 0),
            "Да" if student.get('academic_debt', False) else "Нет",
            "Да" if student.get('discipline_violation', False) else "Нет",
            student.get('study_achievements', 0),
            student.get('science_achievements', 0),
            student.get('sport_achievements', 0),
            student.get('ipd', 0),
            student.get('scholarship', 0),
            student.get('status', 'Не рассчитан'),
            "; ".join(student.get('blocks', []))
        ])
    output.seek(0)
    from flask import Response
    return Response(output.getvalue(), mimetype='text/csv',
                    headers={"Content-Disposition": "attachment;filename=scholarship_results.csv"})

if __name__ == '__main__':
    # Создаём тестовые данные, если их нет
    if not os.path.exists(STUDENTS_FILE):
        test_data = {
            'students': [
                {
                    'id': 1, 'name': 'Иванов Иван', 'group': 'Группа 1',
                    'avg_grade': 4.8, 'academic_debt': False, 'discipline_violation': False,
                    'study_achievements': 90, 'science_achievements': 95, 'sport_achievements': 20,
                    'ipd': 0, 'scholarship': 0, 'status': 'Не рассчитан'
                },
                {
                    'id': 2, 'name': 'Петрова Анна', 'group': 'Группа 1',
                    'avg_grade': 4.2, 'academic_debt': False, 'discipline_violation': False,
                    'study_achievements': 70, 'science_achievements': 60, 'sport_achievements': 80,
                    'ipd': 0, 'scholarship': 0, 'status': 'Не рассчитан'
                },
                {
                    'id': 3, 'name': 'Сидоров Сергей', 'group': 'Группа 2',
                    'avg_grade': 4.5, 'academic_debt': True, 'discipline_violation': False,
                    'study_achievements': 100, 'science_achievements': 100, 'sport_achievements': 100,
                    'ipd': 0, 'scholarship': 0, 'status': 'Не рассчитан'
                }
            ],
            'settings': CONFIG
        }
        save_students(test_data)
    app.run(debug=True, port=5000)
