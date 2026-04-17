from flask import Flask, render_template_string, request, jsonify, session, redirect, url_for
from datetime import datetime
import json
import os

app = Flask(__name__)
app.secret_key = 'your-secret-key-here-change-in-production'

# ==================== КОНФИГУРАЦИЯ ====================
CONFIG = {
    'min_attendance_percent': 50,
    'min_labs_percent': 60,
    'pass_score': 60,
    'auto_pass_score': 90,
    'weights': {
        'labs': 0.3,
        'attendance': 0.2,
        'tests': 0.2,
        'activity': 0.1,
        'lecture_notes': 0.2
    }
}

# ==================== ДАННЫЕ ====================
STUDENTS_FILE = 'students_data.json'


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
def calculate_grade(student, weights, config):
    """Расчет итогового балла и статуса зачета"""

    # Проверка блокирующих факторов
    blocks = []

    # 1. Академическая задолженность
    if student.get('academic_debt', False):
        blocks.append("Академическая задолженность за прошлый семестр")

    # 2. Посещаемость
    attendance = student.get('attendance', 0)
    if attendance < config['min_attendance_percent']:
        blocks.append(f"Посещаемость ниже {config['min_attendance_percent']}% (текущая: {attendance}%)")

    # 3. Лабораторные работы
    labs_done = student.get('labs_done', 0)
    labs_total = student.get('labs_total', 10)
    labs_percent = (labs_done / labs_total * 100) if labs_total > 0 else 0
    if labs_percent < config['min_labs_percent']:
        blocks.append(f"Сдано менее {config['min_labs_percent']}% лабораторных работ (текущая: {labs_percent:.1f}%)")

    # 4. Конспекты
    lecture_notes = student.get('lecture_notes', 0)
    if lecture_notes < 100:
        blocks.append("Конспекты лекций сданы не в полном объеме")

    # Если есть блокирующие факторы - автоматический незачёт
    if blocks:
        return {
            'status': 'Незачёт',
            'score': 0,
            'blocks': blocks,
            'details': None
        }

    # Расчёт взвешенной оценки
    labs_score = (labs_done / labs_total * 100) if labs_total > 0 else 0
    attendance_score = attendance
    tests_score = student.get('tests_score', 0)
    activity_score = student.get('activity', 0) * 10  # 0-10 -> 0-100
    lecture_notes_score = lecture_notes

    total_score = (
            weights['labs'] * labs_score +
            weights['attendance'] * attendance_score +
            weights['tests'] * tests_score +
            weights['activity'] * activity_score +
            weights['lecture_notes'] * lecture_notes_score
    )

    # Проверка на автоматический зачёт
    if total_score >= config['auto_pass_score']:
        status = 'Зачёт (автоматический)'
    elif total_score >= config['pass_score']:
        status = 'Зачёт'
    else:
        status = 'Незачёт'

    return {
        'status': status,
        'score': round(total_score, 2),
        'blocks': blocks,
        'details': {
            'labs_score': round(labs_score, 2),
            'attendance_score': attendance_score,
            'tests_score': tests_score,
            'activity_score': activity_score,
            'lecture_notes_score': lecture_notes_score
        }
    }


# ==================== HTML ШАБЛОНЫ ====================
INDEX_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>Система расчёта зачётов студентов</title>
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
        <h1>🎓 Система расчёта зачётов студентов</h1>

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
                    <label>Лабораторные работы (сдано/всего):</label>
                    <input type="number" name="labs_done" placeholder="Сдано" required> / 
                    <input type="number" name="labs_total" placeholder="Всего" required>
                </div>
                <div class="form-group">
                    <label>Посещаемость (%):</label>
                    <input type="number" name="attendance" step="any" min="0" max="100" required>
                </div>
                <div class="form-group">
                    <label>Тесты (%):</label>
                    <input type="number" name="tests_score" step="any" min="0" max="100" required>
                </div>
                <div class="form-group">
                    <label>Активность (0-10):</label>
                    <input type="number" name="activity" step="any" min="0" max="10" required>
                </div>
                <div class="form-group">
                    <label>Конспекты (%):</label>
                    <input type="number" name="lecture_notes" step="any" min="0" max="100" required>
                </div>
                <div class="form-group">
                    <label>Академическая задолженность:</label>
                    <select name="academic_debt">
                        <option value="false">Нет</option>
                        <option value="true">Да</option>
                    </select>
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
            html += '<h3>Коэффициенты:</h3>';
            for (let [key, value] of Object.entries(settings.weights)) {
                html += `<label>${key}: <input type="number" step="0.05" name="${key}" value="${value}" class="weight-input"></label><br>`;
            }
            html += '<h3>Пороговые значения:</h3>';
            html += `<label>Мин. посещаемость (%): <input type="number" name="min_attendance_percent" value="${settings.min_attendance_percent}"></label><br>`;
            html += `<label>Мин. лабораторные (%): <input type="number" name="min_labs_percent" value="${settings.min_labs_percent}"></label><br>`;
            html += `<label>Порог зачёта: <input type="number" name="pass_score" value="${settings.pass_score}"></label><br>`;
            html += `<label>Авто-зачёт (баллов): <input type="number" name="auto_pass_score" value="${settings.auto_pass_score}"></label><br>`;
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

    # Преобразуем данные для отображения
    students_html = '''
    <table>
        <thead>
            <tr>
                <th>ФИО</th><th>Группа</th><th>Лабораторные</th><th>Посещаемость</th>
                <th>Тесты</th><th>Активность</th><th>Конспекты</th><th>Долг</th>
                <th>Итоговый балл</th><th>Статус</th><th>Действия</th>
            </tr>
        </thead>
        <tbody>
    '''

    for student in data['students']:
        status_class = 'status-pass' if 'Зачёт' in student.get('grade_status', '') else 'status-fail'
        students_html += f'''
            <tr>
                <td>{student['name']}</td>
                <td>{student['group']}</td>
                <td>{student.get('labs_done', 0)}/{student.get('labs_total', 10)}</td>
                <td>{student.get('attendance', 0)}%</td>
                <td>{student.get('tests_score', 0)}%</td>
                <td>{student.get('activity', 0)}/10</td>
                <td>{student.get('lecture_notes', 0)}%</td>
                <td>{"Да" if student.get('academic_debt', False) else "Нет"}</td>
                <td>{student.get('grade_score', 0)}</td>
                <td class="{status_class}">{student.get('grade_status', 'Не рассчитан')}</td>
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

    # Генерируем ID
    student['id'] = max([s.get('id', 0) for s in data['students']] + [0]) + 1
    student['grade_status'] = 'Не рассчитан'
    student['grade_score'] = 0

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
            result = calculate_grade(student, data['settings']['weights'], data['settings'])
            student['grade_status'] = result['status']
            student['grade_score'] = result['score']
            student['grade_blocks'] = result['blocks']
            break

    save_students(data)
    return jsonify({'success': True})


@app.route('/api/calculate_all', methods=['POST'])
def calculate_all():
    data = load_students()
    for student in data['students']:
        result = calculate_grade(student, data['settings']['weights'], data['settings'])
        student['grade_status'] = result['status']
        student['grade_score'] = result['score']
        student['grade_blocks'] = result['blocks']

    save_students(data)
    return jsonify({'success': True})


@app.route('/api/settings', methods=['GET', 'POST'])
def settings():
    data = load_students()

    if request.method == 'GET':
        return jsonify(data['settings'])
    else:
        new_settings = request.json
        for key in new_settings:
            if key in data['settings']:
                data['settings'][key] = new_settings[key]
            elif key in data['settings']['weights']:
                data['settings']['weights'][key] = new_settings[key]
        save_students(data)
        return jsonify({'success': True})


@app.route('/export/csv')
def export_csv():
    import csv
    from io import StringIO

    data = load_students()
    output = StringIO()
    writer = csv.writer(output)

    writer.writerow(['ФИО', 'Группа', 'Лабораторные', 'Посещаемость%', 'Тесты%',
                     'Активность', 'Конспекты%', 'Академический долг',
                     'Итоговый балл', 'Статус', 'Блокирующие факторы'])

    for student in data['students']:
        writer.writerow([
            student['name'], student['group'],
            f"{student.get('labs_done', 0)}/{student.get('labs_total', 10)}",
            student.get('attendance', 0), student.get('tests_score', 0),
            student.get('activity', 0), student.get('lecture_notes', 0),
            "Да" if student.get('academic_debt', False) else "Нет",
            student.get('grade_score', 0), student.get('grade_status', 'Не рассчитан'),
            "; ".join(student.get('grade_blocks', []))
        ])

    output.seek(0)
    from flask import Response
    return Response(output.getvalue(), mimetype='text/csv',
                    headers={"Content-Disposition": "attachment;filename=students_results.csv"})


if __name__ == '__main__':
    # Создаём тестовые данные, если их нет
    if not os.path.exists(STUDENTS_FILE):
        test_data = {
            'students': [
                {
                    'id': 1, 'name': 'Иванов Иван', 'group': 'Группа 1',
                    'labs_done': 8, 'labs_total': 10, 'attendance': 85,
                    'tests_score': 78, 'activity': 7, 'lecture_notes': 100,
                    'academic_debt': False, 'grade_status': 'Не рассчитан', 'grade_score': 0
                },
                {
                    'id': 2, 'name': 'Петрова Анна', 'group': 'Группа 1',
                    'labs_done': 4, 'labs_total': 10, 'attendance': 45,
                    'tests_score': 65, 'activity': 6, 'lecture_notes': 80,
                    'academic_debt': False, 'grade_status': 'Не рассчитан', 'grade_score': 0
                },
                {
                    'id': 3, 'name': 'Сидоров Сергей', 'group': 'Группа 2',
                    'labs_done': 10, 'labs_total': 10, 'attendance': 95,
                    'tests_score': 92, 'activity': 9, 'lecture_notes': 100,
                    'academic_debt': True, 'grade_status': 'Не рассчитан', 'grade_score': 0
                }
            ],
            'settings': CONFIG
        }
        save_students(test_data)

    app.run(debug=True, port=5000)