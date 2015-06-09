import requests
from lxml import html
from collections import namedtuple

BASE_URL = 'https://www.edmodo.com'
ASSIGNMENT_URL = '{}/assignment/ajax-get-submission-info'.format(BASE_URL)
FILES_URL = '{}/file'.format(BASE_URL)
GRADE_URL = '{}/assignment/ajax-grade-assignment'.format(BASE_URL)
MEMBERS_URL = '{}/members/index?group_id={{}}&layout=false&view=group/sections/members'.format(BASE_URL)

Member = namedtuple('Member', ['id', 'name'])

def is_student(name):
        return 'mr' not in name

def get_ids_from_members_page(text):
    tree = html.fromstring(text)
    for x in tree.xpath('//a[@class="name text-15"]'):
        member_id, member_name = x.attrib['href'][-8:], x.text.replace(' ', '_').lower()
        if is_student(member_name):
            yield Member(member_id, member_name)

class EdmodoGroup:
    def __init__(self, group_id, user, pswd):
        self._s = requests.Session()
        self.group_id = group_id
        self.members = None
        self.authenticate(user, pswd)

    def authenticate(self, user, pswd):
        s = self._s
        user_data = {
            'username': user,
            'password': pswd
        }
        s.post(BASE_URL, data=user_data)
        r = s.get(BASE_URL.format('/home'))
        s.headers['x-csrf-token'] = r.headers['x-csrf-token']

    def get_group_members(self):
        url = MEMBERS_URL.format(self.group_id)
        r = self._s.get(url)
        if not r.ok:
            raise Exception('Failed to get group members')

        self.members = members = list(get_ids_from_members_page(r.text))
        return members

    def get_members_assignments(self, assignment_id):
        if not self.members:
            members = self.get_group_members()

        s = self._s
        s.headers.update({"Content-Type": "application/x-www-form-urlencoded",
                          'charset': 'UTF-8'
                          })

        data = {'assignment_id': assignment_id}

        for member in members:
            data['user_id'] = member.id
            r = s.post(ASSIGNMENT_URL, data=data)
            if r.ok and r.content:
                files = r.json().get('files')
                if files:
                    files_ids = [f['fingerprint'] for f in files[0]]
                    for file_ids in files_ids:
                        r = s.get(FILES_URL, params={'id': file_ids}, stream=True)
                        if r.ok:
                            yield {'student_id': member.id, 'student_name': member.name, 'file': r.raw}

    def set_assignment_grade(self, assignment_id, assignment):
        s = self._s
        s.headers.update({"Content-Type": "application/x-www-form-urlencoded"})

        grade_score, grade_total = assignment['grade']
        data = {
            'assignment_id': assignment_id,
            'grade_score': grade_score,
            'grade_total': grade_total,
            'user_assignment_id': '',
            'user_id': assignment['student_id'],
        }

        r = s.post(GRADE_URL, data=data)
        if r.ok:
            print('Posted {} grade: {}'.format(assignment['student_name'], assignment['grade']))