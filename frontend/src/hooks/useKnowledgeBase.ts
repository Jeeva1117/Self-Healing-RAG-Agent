import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { knowledgeBaseService } from '@/services/knowledgeBaseService';

export function useKnowledgeBases(offset = 0, limit = 50) {
  return useQuery({
    queryKey: ['knowledge-bases', offset, limit],
    queryFn: () => knowledgeBaseService.listKnowledgeBases(offset, limit),
    staleTime: 30000,
  });
}

export function useKnowledgeBase(id?: string) {
  return useQuery({
    queryKey: ['knowledge-base', id],
    queryFn: () => (id ? knowledgeBaseService.getKnowledgeBase(id) : null),
    enabled: Boolean(id),
  });
}

export function useCreateKnowledgeBase() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: { name: string; description?: string }) =>
      knowledgeBaseService.createKnowledgeBase(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['knowledge-bases'] });
    },
  });
}

export function useDeleteKnowledgeBase() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => knowledgeBaseService.deleteKnowledgeBase(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['knowledge-bases'] });
      queryClient.invalidateQueries({ queryKey: ['documents'] });
    },
  });
}

export function useDocuments(kbId?: string, offset = 0, limit = 50) {
  return useQuery({
    queryKey: ['documents', kbId, offset, limit],
    queryFn: () => (kbId ? knowledgeBaseService.listDocuments(kbId, offset, limit) : null),
    enabled: Boolean(kbId),
    refetchInterval: (query) => {
      // Automatically poll every 3 seconds if any document is in PROCESSING or UPLOADED status
      const data = query.state.data;
      const hasPending = data?.items?.some(
        (doc) => doc.status === 'PROCESSING' || doc.status === 'UPLOADED'
      );
      return hasPending ? 3000 : false;
    },
  });
}

export function useDocument(docId?: string) {
  return useQuery({
    queryKey: ['document', docId],
    queryFn: () => (docId ? knowledgeBaseService.getDocument(docId) : null),
    enabled: Boolean(docId),
  });
}

export function useDocumentChunks(docId?: string, offset = 0, limit = 50) {
  return useQuery({
    queryKey: ['document-chunks', docId, offset, limit],
    queryFn: () => (docId ? knowledgeBaseService.getDocumentChunks(docId, offset, limit) : null),
    enabled: Boolean(docId),
  });
}

export function useUploadDocument(kbId?: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (file: File) => {
      if (!kbId) throw new Error('Knowledge Base ID is required to upload');
      return knowledgeBaseService.uploadDocument(kbId, file);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['documents', kbId] });
      queryClient.invalidateQueries({ queryKey: ['knowledge-bases'] });
      queryClient.invalidateQueries({ queryKey: ['knowledge-base', kbId] });
    },
  });
}

export function useDeleteDocument(kbId?: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (docId: string) => knowledgeBaseService.deleteDocument(docId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['documents', kbId] });
      queryClient.invalidateQueries({ queryKey: ['knowledge-bases'] });
      queryClient.invalidateQueries({ queryKey: ['knowledge-base', kbId] });
    },
  });
}

export function useReprocessDocument(kbId?: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (docId: string) => knowledgeBaseService.reprocessDocument(docId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['documents', kbId] });
    },
  });
}
