import pytest

from utils.read_yaml import read_case

def to_login_params(file_path : str = 'login_cases.yaml') -> list:
    cases = read_case(file_path)['test_cases']
    print(cases)
    return [
        pytest.param(
            c['data']['user_name'],
            c['data']['passwd'],
            c['validation'][1]['contains']['msg_code'],
            c['validation'][0]['contains']['msg'],
            id = c['case_name']
        )
        for c in cases
    ]


def to_user_add_params(file_path : str = 'add_user_cases.yaml') -> list:
    cases = read_case(file_path)['test_cases']
    print(cases)
    return [
        pytest.param(
            {'user_name': c['data']['user_name']},
            c['validation'][1]['contains']['msg_code'],
            c['validation'][0]['contains']['msg'],
            c['token_type'],
            id = c['case_name']
        )
        for c in cases
    ]
# if __name__ == "__main__":
#     CASES = to_login_params()
#     print(CASES)
#     CASES = to_user_add_params()
#     print(CASES)