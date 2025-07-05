def add_leading_spaces_to_file(filename):
    with open(filename, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    new_lines = []
    for line in lines:
        stripped = line.rstrip('\n')
        # 빈 줄이면 그대로
        if stripped.strip() == '':
            new_lines.append(line)
        # 앞에 스페이스 2개 없으면 추가
        elif not stripped.startswith('  '):
            new_lines.append('  ' + stripped + '\n')
        else:
            new_lines.append(line)

    with open(filename, 'w', encoding='utf-8') as f:
        f.writelines(new_lines)



