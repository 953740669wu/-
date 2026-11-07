"""Forward saved-storage inventory for one strict step, outside timing observations."""
from collections import Counter


class SavedStorage:
    def __init__(self, model, inputs):
        self.weights = {self.storage(p)[0] for p in model.parameters()}
        self.inputs = {self.storage(t)[0] for t in inputs}
        self.storages = {}
        self.forward_closed = False

    @staticmethod
    def storage(tensor):
        storage = tensor.untyped_storage()
        return storage.data_ptr(), storage.nbytes()

    def pack(self, tensor):
        if not self.forward_closed:
            ptr, size = self.storage(tensor)
            role = "weight" if ptr in self.weights else "input" if ptr in self.inputs else "other"
            self.storages[ptr] = (role, size, tuple(tensor.shape))
        return tensor.detach()

    def unpack(self, tensor):
        self.forward_closed = True
        return tensor

    def summary(self, model, optimizer):
        sizes, largest = Counter(), Counter()
        for role, size, shape in self.storages.values():
            sizes[role] += size
            if role == "other" and size:
                largest[(size, shape)] += 1
        def nbytes(tensor):
            return tensor.numel() * tensor.element_size()
        return dict(saved_forward_storage_bytes=dict(sizes),
                    other_largest=[dict(bytes=s, representative_view_shape=d, storages=n)
                                   for (s, d), n in sorted(largest.items(), reverse=True)[:12]],
                    parameter_bytes=sum(nbytes(p) for p in model.parameters()),
                    parameter_gradient_bytes=sum(nbytes(p.grad) for p in model.parameters()),
                    optimizer_tensor_bytes=sum(nbytes(t) for state in optimizer.state.values() for t in state.values()))
