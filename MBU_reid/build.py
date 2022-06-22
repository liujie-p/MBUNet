import logging
import pdb
import torch
from torch._six import container_abcs, string_classes, int_classes
from torch.utils.data import DataLoader

from MBU_reid import samplers
from fastreid.data.datasets import DATASET_REGISTRY
from fastreid.data.transforms import build_transforms
from MBU_reid.dataset import MBUDataset, data_prefetcher


def build_reid_train_loader(cfg):
    train_transforms = build_transforms(cfg, is_train=True)

    logger = logging.getLogger(__name__)
    train_items = list()
    for d in cfg.DATASETS.NAMES:
        logger.info('prepare training set {}'.format(d))
        print('preparing training set...')
        dataset = DATASET_REGISTRY.get(d)(cfg)
        print(dataset)
        train_items.extend(dataset.train)
       

    train_set = MBUDataset(train_items, train_transforms, mode='train', relabel=True)

    num_workers = cfg.DATALOADER.NUM_WORKERS
    batch_size = cfg.SOLVER.IMS_PER_BATCH
    num_instance = cfg.DATALOADER.NUM_INSTANCE

    if cfg.DATALOADER.PK_SAMPLER:
        data_sampler = samplers.RandomIdentitySampler(train_set.img_items, batch_size, num_instance)
    else:
        data_sampler = samplers.TrainingSampler(len(train_set))
    batch_sampler = torch.utils.data.sampler.BatchSampler(data_sampler, batch_size, True)

    train_loader = torch.utils.data.DataLoader(
        train_set,
        num_workers=num_workers,
        batch_sampler=batch_sampler,
        collate_fn=fast_batch_collator,
    )
    return data_prefetcher(cfg, train_loader)


def build_reid_test_loader(cfg, dataset_name):
    test_transforms = build_transforms(cfg, is_train=False)

    logger = logging.getLogger(__name__)
    logger.info('prepare test set {}'.format(dataset_name))
    print('preparing test set...')
    dataset = DATASET_REGISTRY.get(dataset_name)(cfg)
    print(dataset)
    test_items = dataset.query + dataset.gallery

    test_set = MBUDataset(test_items, test_transforms, mode='test', relabel=False)

    num_workers = cfg.DATALOADER.NUM_WORKERS
    batch_size = cfg.TEST.IMS_PER_BATCH
    data_sampler = samplers.InferenceSampler(len(test_set))
    batch_sampler = torch.utils.data.BatchSampler(data_sampler, batch_size, False)
    test_loader = DataLoader(
        test_set,
        batch_sampler=batch_sampler,
        num_workers=num_workers,
        collate_fn=fast_batch_collator)
    return data_prefetcher(cfg, test_loader), len(dataset.query)


def trivial_batch_collator(batch):
    """
    A batch collator that does nothing.
    """
    return batch


def fast_batch_collator(batched_inputs):
    """
    A simple batch collator for most common reid tasks
    """

    elem = batched_inputs[0]
    if isinstance(elem, torch.Tensor):
        out = torch.zeros((len(batched_inputs), *elem.size()), dtype=elem.dtype)
        for i, tensor in enumerate(batched_inputs):
            out[i] += tensor
        return out

    elif isinstance(elem, container_abcs.Mapping):
        return {key: fast_batch_collator([d[key] for d in batched_inputs]) for key in elem}

    elif isinstance(elem, float):
        return torch.tensor(batched_inputs, dtype=torch.float64)
    elif isinstance(elem, int_classes):
        return torch.tensor(batched_inputs)
    elif isinstance(elem, string_classes):
        return batched_inputs
