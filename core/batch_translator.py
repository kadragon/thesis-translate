import json
import logging
import time
import os
from openai import OpenAI
from core.openai_translator import OpenAITranslator

class BatchTranslator:
    def __init__(self, input_file: str, output_file: str = '_result_text_ko.txt', max_token_length: int = 8000):
        self.client = OpenAI()
        self.input_file = input_file
        self.output_file = output_file
        self.max_token_length = max_token_length
        self.translator = OpenAITranslator()

    def create_batch_requests(self, batch_input_file: str):
        requests = []
        with open(self.input_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        buffer = ""
        for line in lines:
            if len(buffer) + len(line) > self.max_token_length:
                requests.append(self._create_request(buffer))
                buffer = ""
            buffer += line

        if buffer:
            requests.append(self._create_request(buffer))

        with open(batch_input_file, 'w', encoding='utf-8') as f:
            for request in requests:
                f.write(json.dumps(request) + '\n')

    def _create_request(self, text: str):
        prompt = self.translator.PROMPT_TEMPLATE.format(glossary=self.translator.glossary, text=text)
        return {
            "custom_id": f"request-{time.time()}",
            "method": "POST",
            "url": "/v1/chat/completions",
            "body": {
                "model": self.translator.model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": self.translator.temperature,
            }
        }

    def translate(self):
        batch_input_file = "batch_input.jsonl"
        self.create_batch_requests(batch_input_file)

        batch_file = self.client.files.create(
            file=open(batch_input_file, "rb"),
            purpose="batch"
        )

        batch = self.client.batches.create(
            input_file_id=batch_file.id,
            endpoint="/v1/chat/completions",
            completion_window="24h"
        )

        logging.info(f"Batch job created: {batch.id}")

        while True:
            batch = self.client.batches.retrieve(batch.id)
            if batch.status == 'completed':
                break
            elif batch.status in ['failed', 'expired', 'cancelling', 'cancelled']:
                logging.error(f"Batch job failed with status: {batch.status}")
                return
            logging.info(f"Batch job status: {batch.status}, waiting...")
            time.sleep(30)

        result_file_id = batch.output_file_id
        if result_file_id:
            result_content = self.client.files.content(result_file_id).read()
            
            # 기존 파일 덮어쓰기
            with open(self.output_file, 'w', encoding='utf-8') as f:
                results = result_content.decode('utf-8').strip().split('\n')
                for res in results:
                    if not res:
                        continue
                    try:
                        data = json.loads(res)
                        content = data['response']['body']['choices'][0]['message']['content']
                        f.write(content + '\n\n')
                    except (json.JSONDecodeError, KeyError) as e:
                        logging.error(f"Error parsing batch result line: {res}, error: {e}")

            logging.info(f"Batch translation completed. Results saved to {self.output_file}")
        else:
            logging.error("Batch job completed but no output file was generated.")
            
        # 임시 파일 삭제
        os.remove(batch_input_file)
