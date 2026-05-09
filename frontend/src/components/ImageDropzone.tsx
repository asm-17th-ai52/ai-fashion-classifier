import { useRef, useState } from "react";
import { useFormContext } from "react-hook-form";
import type { UploadFormValues } from "@/api/schemas";

export default function ImageDropzone() {
  const { setValue, watch, formState: { errors } } = useFormContext<UploadFormValues>();
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);
  const [preview, setPreview] = useState<string | null>(null);

  const imageError = errors.image?.message;

  function handleFile(file: File) {
    if (!file.type.startsWith("image/")) return;
    setValue("image", file, { shouldValidate: true });
    const url = URL.createObjectURL(file);
    setPreview((prev) => {
      if (prev) URL.revokeObjectURL(prev);
      return url;
    });
  }

  function onInputChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (file) handleFile(file);
  }

  function onDrop(e: React.DragEvent) {
    e.preventDefault();
    setDragging(false);
    const file = e.dataTransfer.files?.[0];
    if (file) handleFile(file);
  }

  const currentFile = watch("image");

  return (
    <div className="flex flex-col gap-2 h-full">
      <div
        className={`relative flex flex-col items-center justify-center rounded-2xl border-[1.5px] transition-all duration-200 cursor-pointer min-h-[240px] ${
          dragging
            ? "border-accent-blue bg-accent-blue-soft shadow-glow-sm"
            : imageError
            ? "border-accent-red/50 bg-accent-red-soft"
            : preview
            ? "border-hairline bg-surface"
            : "border-dashed border-hairline hover:border-hairline-strong hover:bg-surface-elevated/50"
        }`}
        onClick={() => inputRef.current?.click()}
        onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        role="button"
        tabIndex={0}
        aria-label="이미지를 드래그하거나 클릭하여 업로드"
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") inputRef.current?.click();
        }}
      >
        {preview ? (
          <img
            src={preview}
            alt="업로드된 착장 이미지 미리보기"
            className="max-h-[240px] max-w-full rounded-xl object-contain"
          />
        ) : (
          <div className="text-center px-6 py-12 select-none">
            <div className="w-11 h-11 rounded-xl bg-surface-elevated border border-hairline flex items-center justify-center mx-auto mb-4">
              <svg className="w-5 h-5 text-mute" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
              </svg>
            </div>
            <p className="text-sm text-body font-medium">사진 드래그 또는 클릭</p>
            <p className="text-xs text-stone mt-1.5">JPEG · PNG · WebP · 최대 10MB</p>
          </div>
        )}
      </div>

      {currentFile && (
        <p className="text-[11px] text-stone font-mono truncate px-1">{currentFile.name}</p>
      )}

      {imageError && (
        <p role="alert" className="text-xs text-accent-red px-1">{imageError}</p>
      )}

      <input
        ref={inputRef}
        type="file"
        accept="image/jpeg,image/png,image/webp"
        className="sr-only"
        aria-label="이미지 파일 선택"
        onChange={onInputChange}
      />
    </div>
  );
}
