import os
import struct

def parse_simple_offset(fs, offset, length):
    fs.seek(offset)
    return fs.read(length)

def get_next_offset(fs, offset, magic_bytes):
    while offset + len(magic_bytes) <= os.fstat(fs.fileno()).st_size:
        fs.seek(offset)
        buffer = fs.read(len(magic_bytes))
        if buffer == magic_bytes:
            return offset
        offset += 1
    return -1

MAGIC_BYTES = b'\x4F\x67\x67\x53'
PAGE_TYPE_BEGIN_STREAM = 0x02
PAGE_TYPE_END_STREAM = 0x04

def process_file(file_path, stop_parsing_on_format_error=True):
    offset = 0
    output_path = os.path.dirname(file_path)
    global_index = 0
    output_streams = {}

    with open(file_path, 'rb') as fs:
        try:
            while (offset := get_next_offset(fs, offset, MAGIC_BYTES)) > -1:
                page_type = parse_simple_offset(fs, offset + 5, 1)[0]
                bitstream_serial_number = struct.unpack_from('<I', parse_simple_offset(fs, offset + 0xE, 4))[0]
                segment_count = parse_simple_offset(fs, offset + 0x1A, 1)[0]

                size_of_all_segments = sum(
                    parse_simple_offset(fs, offset + 0x1B + i, 1)[0] for i in range(segment_count)
                )
                page_size = 0x1B + segment_count + size_of_all_segments

                raw_page_bytes = parse_simple_offset(fs, offset, page_size)

                if page_type & PAGE_TYPE_BEGIN_STREAM == PAGE_TYPE_BEGIN_STREAM:
                    if bitstream_serial_number in output_streams:
                        if stop_parsing_on_format_error:
                            raise struct.error(
                                f"多次找到流开始页面，但没有流结束页面，用于序列号: {bitstream_serial_number:X8}。")
                        else:
                            print(f"警告：对于文件 <{file_path}>，多次找到流开始页面但没有流结束页面，序列号为: {bitstream_serial_number:X8}。")
                    else:
                        file_name_prefix = os.path.splitext(os.path.basename(file_path))[0]
                        output_file_name = os.path.join(output_path, f"{file_name_prefix}_{global_index}.ogg")
                        global_index += 1
                        while os.path.exists(output_file_name):
                            file_name, file_ext = os.path.splitext(output_file_name)
                            output_file_name = f"{file_name}_1{file_ext}"

                        output_streams[bitstream_serial_number] = open(output_file_name, 'wb')
                        output_streams[bitstream_serial_number].write(raw_page_bytes)
                        print(f"正在生成文件: {output_file_name}")
                elif bitstream_serial_number in output_streams:
                    output_streams[bitstream_serial_number].write(raw_page_bytes)
                else:
                    if stop_parsing_on_format_error:
                        raise struct.error(
                            f"找到没有流开始页的流数据页，用于序列号: {bitstream_serial_number:X8}。")
                    else:
                        print(f"警告：对于文件 <{file_path}>，找到没有流开始页的流数据页，序列号为: {bitstream_serial_number:X8}。")

                if page_type & PAGE_TYPE_END_STREAM == PAGE_TYPE_END_STREAM:
                    if bitstream_serial_number in output_streams:
                        output_streams[bitstream_serial_number].write(raw_page_bytes)
                        output_streams[bitstream_serial_number].close()
                        output_streams.pop(bitstream_serial_number)
                    else:
                        if stop_parsing_on_format_error:
                            raise struct.error(
                                f"找到没有流开始页面的流结束页面，用于序列号: {bitstream_serial_number:X8}。")
                        else:
                            print(f"警告：对于文件 <{file_path}>，找到没有流开始页面的流结束页面，序列号为: {bitstream_serial_number:X8}。")

                offset += page_size

            # 关闭所有未关闭的流
            for stream in output_streams.values():
                stream.close()

        except Exception as ex:
            print(f"处理文件 {file_path} 时出现错误: {ex}")
            # 关闭所有未关闭的流
            for stream in output_streams.values():
                stream.close()

if __name__ == "__main__":
    input_path = input("请输入一个有效的文件夹路径: ")
    if not os.path.isdir(input_path):
        print("输入的路径不是一个有效的文件夹。")
    else:
        for root, dirs, files in os.walk(input_path):
            for file in files:
                file_path = os.path.join(root, file)
                process_file(file_path)