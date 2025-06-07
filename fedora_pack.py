import requests
import subprocess
import re
import os
import argparse
from bs4 import BeautifulSoup
from prettytable import PrettyTable

def main():
    #Парсинг аргумента строки
    parser = argparse.ArgumentParser(description='Поиск пакетов')
    parser.add_argument('package_name', help='Пакет, который мы хотим проверить')
    args = parser.parse_args()

    #Первичный поиск
    params = {
        "terms": args.package_name,
        "match": "glob",
        "type": "package"
    }

    response = requests.get(f"https://koji.fedoraproject.org/koji/search", params=params)
    soup = BeautifulSoup(response.text, 'html.parser')
    total_packages = soup.find('strong', string=lambda t: t and 'through 50 of' in t)

    if not (total_packages): #проверка, что пакет существует
        print(f'Пакета с именем "{args.package_name}" не существует')
        exit()

    #Ищем полное количество пакетов и страниц, чтобы прокрутить на другой лист
    total_packages = total_packages.text.split('of')[-1].strip()
    total_packages = int(total_packages)
    total_pages = total_packages // 30 + (total_packages % 30 != 0)
    current_page = 1


    #Получение ID пакета
    q = soup.find('a', href=lambda href: href and 'packageID=' in href)
    href = q['href']
    package_id = href.split('packageID=')[1].split('&')[0]

    package_names = []
    build_ids = []
    pattern = r"\.fc"

    #Получение всех пакетов
    while current_page != 0:
        soup = BeautifulSoup(response.text, 'html.parser')
        for row in soup.select('table.nested.data-list tr.row-odd, table.nested.data-list tr.row-even'):
            link = row.find('a', href=lambda href: href and 'buildinfo?buildID=' in href)
            if link and re.search(pattern, link.text):
                package_names.append(link.text)
                build_id = link['href'].split('buildinfo?buildID=')[1]
                build_ids.append(build_id)

        new_params = {
            "buildStart": 30 * current_page,
            "packageID": int(package_id),
            "buildOrder": "-completion_time",
            "tagOrder": "name",
            "tagStart": "0"
        }
        current_page += 1
        current_page %= (total_pages + 1)
        response = requests.get(f"https://koji.fedoraproject.org/koji/packageinfo", params=new_params)


    total_packages = len(package_names)
    total_pages = total_packages // 30 + (total_packages % 30 != 0)
    flag = True

    #Пользователь вводит имя пакета
    current_page = 1
    while flag:
        os.system('clear')
        table = PrettyTable()
        table.add_column('Номер', [i for i in range((current_page - 1) * 30 + 1, min(total_packages, current_page * 30) + 1)])
        table.add_column('Имя пакета', [package_names[i + 30 * (current_page - 1)] for i in range(min(total_packages - 30 * (current_page - 1), 30))])
        table.add_column('BuiildID', [build_ids[i + 30 * (current_page - 1)] for i in range(min(total_packages - 30 * (current_page - 1), 30))])

        print(f'Пакеты с {(current_page - 1) * 30 + 1} по {min(total_packages, current_page * 50)} из списка всех пакетов ({total_packages}):')
        print(table)
        print(f'Таблица ({current_page} из {total_pages})')
        print('Введите имя пакета или его номер в таблице для установки. Введите "next" для показа следующей страницы.')
        pack_name = input()

        if (pack_name == 'next'): #Обработка следующей страницы
            current_page += 1
            current_page = max(current_page % (total_pages + 1), 1)
        else:
            if (pack_name.isdigit()):
                if (int(pack_name) < total_packages + 1):
                    pack_name = package_names[int(pack_name) - 1]
                    flag = False
                else:
                    print('Ошибка. Такого пакета с таким номером нет. Выберите пакет из списка')
            elif pack_name not in package_names:
                print('Ошибка. Такого пакета нет. Выберите пакет из списка')
            else:
                flag = False

    os.system('clear')

    #Проверка на то, установлен ли данный пакет или нет
    print(f'Вы выбрали пакет {pack_name}. Проверка наличия {args.package_name} в системе...')
    try:
        result = subprocess.run(['rpm', '-qa', args.package_name], capture_output=True, text=True)
        result_bool = bool(result.stdout.strip()) #существует пакет или нет
    except subprocess.SubprocessError as e:
        print(f"Ошибка при проверке пакета: {e}")
        exit()

    #Возможное удаление пакета
    if result_bool:
        print(f'Установлены следующие версии пакета:\n {result.stdout.strip()}. \nУдалить пакет {args.package_name}? Y/N')
        user_reply = input()
        if (user_reply == 'Y'):
            try:
                subprocess.run(['sudo', 'dnf', 'remove', '-y', args.package_name], check=True)
                print('Пакет успешно удален.')

            except subprocess.SubprocessError as e:
                print(f"Ошибка при удалении пакета: {e}")
                exit()


    print(f'Скачать версию пакета {pack_name}? Y/N')
    user_reply = input()

    #Поиск бинарного файла через парсинг
    if (user_reply == 'Y'):

        response = requests.get(f"https://koji.fedoraproject.org/koji/buildinfo", params={ 'buildID' : build_ids[package_names.index(pack_name)] })
        state = (response.text.split('<th>State</th>'))[1] #Определение state и возможности скачать файл
        state = state.split('</td>')[0]

        if ("complete" not in state):
            print(f"Невозможно скачать пакет {pack_name} с сайта (not complete).")
            exit()

        soup = BeautifulSoup(response.text, 'html.parser')
        pack_rpm = pack_name + '.x86_64.rpm' #бинарный файл для соей системы, можно заменить на подходящий

        #Поиск элементов, в которых присутствует данный бинарный файл
        matching_rows = []
        for row in soup.find_all('tr'):
            if pack_rpm in row.get_text():
                matching_rows.append(row)

        if len(matching_rows) == 0:
            print('Нет подходящего пакета для x86_64 или иная ошибка, проверьте сайт на возможность скачивания.')
            exit()

        for td in matching_rows[0].find_all('td'):
            if pack_rpm in td.get_text(strip=True):
             all_links = [a['href'] for a in td.find_all('a', href=True)] #Получение всех возможных ссылок из таблички

        for link in all_links:
            if pack_rpm in link: #Выделение нужно ссылки с бинарным файлом
                print('Мы нашли ссылку:', link)
                download_url = link

        try:
            subprocess.run(['sudo', 'wget', '-q', '--show-progress', download_url, '-O', 'download.rpm'], check=True)
            print('Пакет скачан. Установить? Y/N')
            user_reply = input()
            if (user_reply == 'Y'):
                try:
                    subprocess.run(['sudo', 'dnf', 'install', '-y', './download.rpm'], check=True)
                    subprocess.run(['sudo', 'rm', 'download.rpm'], check=True)
                except subprocess.SubprocessError as e:
                    print(f'Ошибка при установке пакета: {e}. Возможно, версия неактуальна.')
            else:
                exit()
        except subprocess.SubprocessError as e:
            print(f"Ошибка при скачивании пакета: {e}")
            return False



if __name__ == '__main__':
    main()
