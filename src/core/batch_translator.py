import json
import logging
import os
import sys
import time
from pathlib import Path

import tiktoken
from openai import OpenAI

from src import config
from src.core.translation_config import TranslationConfig

logger = logging.getLogger(__name__)


class BatchTranslator:
    def __init__(
        self,
        input_file: str,
        output_file: str = config.OUTPUT_FILE,
        max_token_length: int = config.MAX_TOKEN_LENGTH,
    ):
        self.client = OpenAI()
        self.input_file = input_file
        self.output_file = output_file
        self.max_token_length = max_token_length
        self.config = TranslationConfig()
        self.encoding = tiktoken.get_encoding("cl100k_base")

    def _count_tokens(self, text: str) -> int:
        return len(self.encoding.encode(text))

    def create_batch_requests(self, batch_input_file: str):
        requests = []
        try:
            with Path(self.input_file).open(encoding="utf-8") as f:
                lines = f.readlines()
        except FileNotFoundError:
            logger.exception(f"입력 파일을 찾을 수 없습니다: {self.input_file}")
            raise

        buffer = ""
        for line in lines:
            # 토큰 길이를 사용하여 버퍼 크기 확인
            if self._count_tokens(buffer + line) > self.max_token_length:
                requests.append(self._create_request(buffer))
                buffer = ""
            buffer += line

        if buffer:
            requests.append(self._create_request(buffer))

        with Path(batch_input_file).open("w", encoding="utf-8") as f:
            f.writelines(json.dumps(request) + "\n" for request in requests)

    def _create_request(self, text: str):
        prompt = self.config.PROMPT_TEMPLATE.format(
            glossary=self.config.glossary, text=text
        )
        return {
            "custom_id": f"request-{time.time_ns()}",
            "method": "POST",
            "url": "/v1/chat/completions",
            "body": {
                "model": self.config.model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": self.config.temperature,
            },
        }

    def translate(self):
        batch_input_file = config.BATCH_INPUT_FILE
        try:
            self.create_batch_requests(batch_input_file)

            with Path(batch_input_file).open("rb") as batch_file_obj:
                batch_file = self.client.files.create(
                    file=batch_file_obj, purpose="batch"
                )

            batch = self.client.batches.create(
                input_file_id=batch_file.id,
                endpoint="/v1/chat/completions",
                completion_window="24h",
            )

            logger.info(f"Batch job created: {batch.id}")

            while True:
                batch = self.client.batches.retrieve(batch.id)
                if batch.status == "completed":
                    break
                if batch.status in ["failed", "expired", "cancelling", "cancelled"]:
                    logger.error(f"Batch job failed with status: {batch.status}")
                    return
                logger.info(f"Batch job status: {batch.status}, waiting...")
                time.sleep(30)

            result_file_id = batch.output_file_id
            if result_file_id:
                result_content = self.client.files.content(result_file_id).read()

                with Path(self.output_file).open("w", encoding="utf-8") as f:
                    results = result_content.decode("utf-8").strip().split("\n")
                    for res in results:
                        if not res:
                            continue
                        try:
                            data = json.loads(res)
                            content = data["response"]["body"]["choices"][0]["message"][
                                "content"
                            ]
                            f.write(content + "\n\n")
                        except (json.JSONDecodeError, KeyError) as e:
                            logger.exception(
                                f"Error parsing batch result line: {res}, error: {e}"
                            )

                logger.info(
                    f"Batch translation completed. Results saved to {self.output_file}"
                )
            else:
                logger.error("Batch job completed but no output file was generated.")
        finally:
            batch_input_path = Path(batch_input_file)
            if batch_input_path.exists():
                batch_input_path.unlink()
                logger.info(f"임시 파일 삭제: {batch_input_file}")

    def format_output(self):
        with Path(self.output_file).open(encoding="utf-8") as f:
            lines = f.readlines()

        new_lines = []
        for line in lines:
            stripped = line.rstrip("\n")
            if stripped.strip() == "":
                new_lines.append(line)
            elif not stripped.startswith("  "):
                new_lines.append("  " + stripped + "\n")
            else:
                new_lines.append(line)

        with Path(self.output_file).open("w", encoding="utf-8") as f:
            f.writelines(new_lines)
